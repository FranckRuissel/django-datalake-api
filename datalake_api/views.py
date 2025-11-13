import os
import json
import csv
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.core.management import call_command
from rest_framework import status, generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import LimitOffsetPagination

from .models import DataLakeResource, PermissionEntry
from .serializers import DataLakeResourceSerializer, PermissionSerializer

User = get_user_model()


# ----------------------------
# Permissions
# ----------------------------

class GrantPermissionView(APIView):
    """Accorder une permission à un utilisateur sur une ressource"""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        username = request.data.get('username')
        path = request.data.get('path')
        access = request.data.get('access')
        if not username or not path or not access:
            return Response({'error':'username, path, access required'}, status=400)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error':'user not found'}, status=404)

        # Sécurisation du chemin
        full_path = os.path.normpath(os.path.join(settings.DATA_LAKE_ROOT, path))
        if not full_path.startswith(settings.DATA_LAKE_ROOT):
            return Response({'error':'invalid path'}, status=400)

        res, _ = DataLakeResource.objects.get_or_create(
            path=path, 
            is_folder=os.path.isdir(full_path)
        )
        perm, created = PermissionEntry.objects.get_or_create(
            user=user, resource=res, access=access
        )
        return Response(PermissionSerializer(perm).data, status=201)


class RevokePermissionView(APIView):
    """Révoquer une permission sur une ressource"""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        username = request.data.get('username')
        path = request.data.get('path')
        access = request.data.get('access')
        if not username or not path or not access:
            return Response({'error':'username, path, access required'}, status=400)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error':'user not found'}, status=404)

        try:
            res = DataLakeResource.objects.get(path=path)
        except DataLakeResource.DoesNotExist:
            return Response({'error':'resource not found'}, status=404)

        PermissionEntry.objects.filter(user=user, resource=res, access=access).delete()
        return Response({'status':'permission revoked'}, status=200)


# ----------------------------
# Data Lake Resources
# ----------------------------

class ListResourcesView(generics.ListAPIView):
    """Lister toutes les ressources du Data Lake"""
    serializer_class = DataLakeResourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = DataLakeResource.objects.all()


class RetrieveDataView(APIView):
    """Lire un fichier ou un dossier du Data Lake avec filtres, projection et pagination"""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = LimitOffsetPagination

    def get(self, request):
        path = request.query_params.get('path')
        if not path:
            return Response({'error':'path required'}, status=400)

        # Sécurisation du chemin
        full_path = os.path.normpath(os.path.join(settings.DATA_LAKE_ROOT, path))
        if not full_path.startswith(settings.DATA_LAKE_ROOT):
            return Response({'error':'invalid path'}, status=400)

        try:
            res = DataLakeResource.objects.get(path=path)
        except DataLakeResource.DoesNotExist:
            return Response({'error':'resource not found'}, status=404)

        # Vérifier permission lecture
        if not PermissionEntry.objects.filter(user=request.user, resource=res, access='read').exists():
            return Response({'error':'forbidden'}, status=403)

        if not os.path.exists(full_path):
            return Response({'error':'file not found'}, status=404)

        # Lecture du contenu
        data = []
        if os.path.isdir(full_path):
            files = os.listdir(full_path)
            return Response({'directory': path, 'files': files})

        try:
            if full_path.endswith(('.json', '.jsonl')):
                with open(full_path, 'r', encoding='utf-8') as f:
                    try:
                        obj = json.load(f)
                        data = obj if isinstance(obj, list) else [obj]
                    except Exception:
                        f.seek(0)
                        for line in f:
                            if line.strip():
                                data.append(json.loads(line))
            elif full_path.endswith('.csv'):
                with open(full_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        data.append(row)
            else:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return Response({'raw': f.read()})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

        # Filtres
        filters = request.query_params.get('filters')
        if filters:
            try:
                filt = json.loads(filters)
                def match(item):
                    for k,v in filt.items():
                        if k not in item:
                            return False
                        if isinstance(v, dict):
                            if 'gt' in v and not (float(item.get(k,0))>float(v['gt'])):
                                return False
                            if 'lt' in v and not (float(item.get(k,0))<float(v['lt'])):
                                return False
                            if 'eq' in v and not (str(item.get(k))==str(v['eq'])):
                                return False
                        else:
                            if str(item.get(k))!=str(v):
                                return False
                    return True
                data = [it for it in data if match(it)]
            except Exception:
                pass

        # Projection
        projection = request.query_params.get('projection')
        if projection:
            keys = [k.strip() for k in projection.split(',')]
            data = [{k: it.get(k) for k in keys} for it in data]

        # Pagination
        paginator = LimitOffsetPagination()
        paginator.page_size = 10
        result_page = paginator.paginate_queryset(data, request)
        return paginator.get_paginated_response(result_page)


# ----------------------------
# Metrics
# ----------------------------

class MoneyLast5MinView(APIView):
    """Somme des transactions des 5 dernières minutes"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            with connection.cursor() as c:
                c.execute("""SELECT SUM(amount) FROM transactions WHERE timestamp >= datetime('now','-5 minutes')""")
                row = c.fetchone()
                total = row[0] if row and row[0] is not None else 0
        except Exception:
            total = None
        return Response({'sum_last_5_min': total})


# ----------------------------
# Repush
# ----------------------------

@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def repush_transaction_view(request):
    """Réinjection d’une transaction"""
    tx_id = request.data.get('transaction_id')
    if not tx_id:
        return Response({'error':'transaction_id required'}, status=400)
    call_command('repush_transaction', tx_id)
    return Response({'status':'ok', 'transaction_id': tx_id})


# ----------------------------
# Search
# ----------------------------

class SearchView(APIView):
    """Recherche textuelle dans le Data Lake"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        q = request.query_params.get('q')
        start_date = request.query_params.get('start_date')
        if not q:
            return Response({'error':'q parameter required'}, status=400)

        root = settings.DATA_LAKE_ROOT
        results = []
        for dirpath, dirs, files in os.walk(root):
            for fname in files:
                if fname.endswith(('.json','.jsonl','.csv','.txt')):
                    fp = os.path.join(dirpath, fname)
                    try:
                        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if q.lower() in content.lower():
                                results.append({'file': os.path.relpath(fp, root)})
                    except Exception:
                        pass

        # Pagination
        paginator = LimitOffsetPagination()
        paginator.page_size = 20
        result_page = paginator.paginate_queryset(results, request)
        return paginator.get_paginated_response(result_page)
