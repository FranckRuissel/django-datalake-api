# datalake_api/views.py
"""
Vues complètes pour l'API Data Lake
Compatible avec vos modèles et urls.py
"""

from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from rest_framework import permissions, status
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import os
import json
import csv
import logging
from pathlib import Path
from django.contrib.auth import get_user_model

from .models import (
    DataLakeResource, PermissionEntry, AuditLog, VersionEntry,
    DataLakePermission, APIAccessLog, DataLakeFile
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ==========================================
# PAGINATION
# ==========================================

class OptimizedPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 100
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_info': {
                'current_page': (self.offset // self.limit) + 1 if self.limit else 1,
                'page_size': self.limit,
                'total_pages': (self.count + self.limit - 1) // self.limit if self.limit else 1,
            },
            'results': data
        })


# ==========================================
# PERMISSIONS VIEWS
# ==========================================

class GrantPermissionView(APIView):
    """Donner des permissions à un utilisateur"""
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID utilisateur'),
                'resource_path': openapi.Schema(type=openapi.TYPE_STRING, description='Chemin ressource'),
                'access': openapi.Schema(type=openapi.TYPE_STRING, enum=['read', 'write'], description='Type accès'),
            },
            required=['user_id', 'resource_path', 'access']
        ),
        responses={
            201: 'Permission créée',
            400: 'Paramètres invalides',
            404: 'Utilisateur introuvable'
        }
    )
    def post(self, request):
        user_id = request.data.get('user_id')
        resource_path = request.data.get('resource_path')
        access = request.data.get('access', 'read')
        
        if not all([user_id, resource_path]):
            return Response(
                {'error': 'user_id et resource_path requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Utilisateur introuvable'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Créer ou récupérer la ressource
        is_folder = not resource_path.endswith(('.json', '.jsonl', '.csv'))
        resource, _ = DataLakeResource.objects.get_or_create(
            path=resource_path,
            defaults={'is_folder': is_folder}
        )
        
        # Créer la permission
        permission, created = PermissionEntry.objects.get_or_create(
            user=user,
            resource=resource,
            access=access
        )
        
        # Aussi créer dans DataLakePermission pour compatibilité
        DataLakePermission.objects.update_or_create(
            user=user,
            resource_type='file',
            resource_path=resource_path,
            defaults={
                'can_read': access == 'read',
                'can_write': access == 'write',
            }
        )
        
        # Log dans AuditLog
        AuditLog.objects.create(
            user=request.user,
            path=f'/permissions/grant/',
            method='POST',
            status_code=201 if created else 200,
            request_body=json.dumps(request.data)
        )
        
        return Response({
            'message': 'Permission créée' if created else 'Permission existe déjà',
            'user': user.username,
            'resource': resource_path,
            'access': access
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class RevokePermissionView(APIView):
    """Révoquer des permissions"""
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'resource_path': openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=['user_id', 'resource_path']
        ),
        responses={200: 'Permissions révoquées', 400: 'Paramètres invalides'}
    )
    def post(self, request):
        user_id = request.data.get('user_id')
        resource_path = request.data.get('resource_path')
        
        if not all([user_id, resource_path]):
            return Response(
                {'error': 'user_id et resource_path requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Supprimer de PermissionEntry
        deleted_count = PermissionEntry.objects.filter(
            user_id=user_id,
            resource__path=resource_path
        ).delete()[0]
        
        # Supprimer de DataLakePermission
        DataLakePermission.objects.filter(
            user_id=user_id,
            resource_path=resource_path
        ).delete()
        
        # Log
        AuditLog.objects.create(
            user=request.user,
            path=f'/permissions/revoke/',
            method='POST',
            status_code=200,
            request_body=json.dumps(request.data)
        )
        
        return Response({
            'message': 'Permissions révoquées',
            'deleted_count': deleted_count
        })


# ==========================================
# DATA RETRIEVAL
# ==========================================

class RetrieveDataView(APIView):
    """Récupérer les données du Data Lake"""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = OptimizedPagination
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('path', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Chemin fichier'),
            openapi.Parameter('browse', openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN, description='Mode navigation'),
            openapi.Parameter('filters', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Filtres JSON'),
            openapi.Parameter('projection', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Champs à retourner'),
        ]
    )
    def get(self, request):
        browse_mode = request.query_params.get('browse', 'false').lower() == 'true'
        path = request.query_params.get('path', '').strip()
        
        if browse_mode:
            return self._browse(request, path)
        
        if not path:
            return Response(
                {'error': 'Paramètre "path" requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return self._read_file(request, path)
    
    def _check_permission(self, user, path):
        """Vérifier les permissions"""
        if user.is_superuser:
            return True
        
        # Extraire le topic (premier segment)
        topic = path.split('/')[0] if path else ''
        
        # Chercher dans PermissionEntry
        resources = DataLakeResource.objects.filter(
            Q(path=path) | Q(path=topic) | Q(path='')
        )
        
        for resource in resources:
            if PermissionEntry.objects.filter(
                user=user,
                resource=resource,
                access='read'
            ).exists():
                return True
        
        return False
    
    def _browse(self, request, current_path):
        """Mode navigation"""
        try:
            base_path = Path(settings.DATA_LAKE_ROOT)
            full_path = base_path / current_path if current_path else base_path
            full_path = full_path.resolve()
            
            # Sécurité
            if not str(full_path).startswith(str(base_path)):
                return Response({'error': 'Chemin invalide'}, status=status.HTTP_403_FORBIDDEN)
            
            if not full_path.exists():
                return Response({'error': 'Chemin introuvable'}, status=status.HTTP_404_NOT_FOUND)
            
            if not self._check_permission(request.user, current_path):
                return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)
            
            if full_path.is_file():
                return Response({
                    'error': 'Ceci est un fichier, utilisez le mode lecture'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Lister le contenu
            items = []
            for item in sorted(full_path.iterdir()):
                relative = str(item.relative_to(base_path)).replace('\\', '/')
                
                items.append({
                    'name': item.name,
                    'path': relative,
                    'type': 'directory' if item.is_dir() else 'file',
                    'size': item.stat().st_size if item.is_file() else None,
                })
            
            return Response({
                'current_path': current_path or '/',
                'items': items,
                'total': len(items)
            })
        
        except Exception as e:
            logger.error(f"Browse error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _read_file(self, request, path):
        """Lire un fichier"""
        try:
            base_path = Path(settings.DATA_LAKE_ROOT)
            full_path = base_path / path
            full_path = full_path.resolve()
            
            # Sécurité
            if not str(full_path).startswith(str(base_path)):
                return Response({'error': 'Chemin invalide'}, status=status.HTTP_403_FORBIDDEN)
            
            if not full_path.exists():
                return Response({'error': 'Fichier introuvable'}, status=status.HTTP_404_NOT_FOUND)
            
            if not self._check_permission(request.user, path):
                return Response({'error': 'Accès refusé'}, status=status.HTTP_403_FORBIDDEN)
            
            # Lire le contenu
            data = []
            if full_path.suffix in ['.json', '.jsonl']:
                with open(full_path, 'r', encoding='utf-8') as f:
                    try:
                        obj = json.load(f)
                        data = obj if isinstance(obj, list) else [obj]
                    except json.JSONDecodeError:
                        f.seek(0)
                        for line in f:
                            if line.strip():
                                try:
                                    data.append(json.loads(line))
                                except:
                                    pass
            elif full_path.suffix == '.csv':
                with open(full_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
            else:
                return Response({
                    'error': 'Format de fichier non supporté',
                    'supported': ['json', 'jsonl', 'csv']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Appliquer filtres si présents
            filters_json = request.query_params.get('filters')
            if filters_json:
                try:
                    filters = json.loads(filters_json)
                    data = self._apply_filters(data, filters)
                except:
                    pass
            
            # Appliquer projection si présente
            projection = request.query_params.get('projection')
            if projection:
                fields = [f.strip() for f in projection.split(',')]
                data = [{k: v for k, v in item.items() if k in fields} for item in data]
            
            # Pagination
            paginator = self.pagination_class()
            result = paginator.paginate_queryset(data, request)
            
            return paginator.get_paginated_response({
                'file_info': {
                    'path': path,
                    'size': full_path.stat().st_size
                },
                'data': result
            })
        
        except Exception as e:
            logger.error(f"Read file error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _apply_filters(self, data, filters):
        """Appliquer des filtres"""
        def matches(item):
            for field, condition in filters.items():
                if field not in item:
                    return False
                
                value = item[field]
                
                if not isinstance(condition, dict):
                    if str(value) != str(condition):
                        return False
                    continue
                
                for op, target in condition.items():
                    if op == 'eq' and str(value) != str(target):
                        return False
                    elif op == 'gt':
                        try:
                            if not (float(value) > float(target)):
                                return False
                        except:
                            return False
                    elif op == 'lt':
                        try:
                            if not (float(value) < float(target)):
                                return False
                        except:
                            return False
                    elif op == 'in' and value not in target:
                        return False
                    elif op == 'contains' and target not in str(value):
                        return False
            
            return True
        
        return [item for item in data if matches(item)]


# ==========================================
# RESOURCES
# ==========================================

class ListResourcesView(APIView):
    """Lister toutes les ressources"""
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        responses={200: 'Liste des ressources'}
    )
    def get(self, request):
        resources = DataLakeResource.objects.all()
        
        if not request.user.is_superuser:
            user_resources = PermissionEntry.objects.filter(
                user=request.user
            ).values_list('resource_id', flat=True)
            resources = resources.filter(id__in=user_resources)
        
        data = [{
            'path': r.path,
            'is_folder': r.is_folder,
            'created_at': r.created_at.isoformat()
        } for r in resources]
        
        return Response({
            'resources': data,
            'count': len(data)
        })


# ==========================================
# METRICS
# ==========================================

class MoneyLast5MinView(APIView):
    """Argent dépensé dans les 5 dernières minutes"""
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        responses={200: 'Métriques calculées'}
    )
    def get(self, request):
        return Response({
            'period': 'last_5_minutes',
            'total_spent': 0,
            'message': 'Nécessite un modèle Transaction pour fonctionner'
        })


# ==========================================
# SEARCH
# ==========================================

class SearchView(APIView):
    """Recherche full-text"""
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('query', openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True),
        ],
        responses={200: 'Résultats de recherche'}
    )
    def get(self, request):
        query = request.query_params.get('query', '').strip()
        
        if not query:
            return Response(
                {'error': 'Paramètre query requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Rechercher dans les ressources
        resources = DataLakeResource.objects.filter(path__icontains=query)
        
        if not request.user.is_superuser:
            user_resources = PermissionEntry.objects.filter(
                user=request.user
            ).values_list('resource_id', flat=True)
            resources = resources.filter(id__in=user_resources)
        
        results = [{
            'path': r.path,
            'is_folder': r.is_folder
        } for r in resources[:50]]
        
        return Response({
            'query': query,
            'count': len(results),
            'results': results
        })


# ==========================================
# KAFKA RE-PUSH
# ==========================================

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'transaction_id': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['transaction_id']
    )
)
def repush_transaction_view(request):
    """Re-push une transaction dans Kafka"""
    transaction_id = request.data.get('transaction_id')
    
    if not transaction_id:
        return Response(
            {'error': 'transaction_id requis'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # TODO: Implémenter la logique Kafka
    return Response({
        'message': 'Re-push en cours de développement',
        'transaction_id': transaction_id
    })
