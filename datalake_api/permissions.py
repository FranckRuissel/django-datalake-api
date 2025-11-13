from rest_framework.permissions import BasePermission
from .models import DataLakeResource, PermissionEntry

class HasDataLakeAccess(BasePermission):
    def has_permission(self, request, view):
        path = getattr(view, 'resource_path', None) or request.query_params.get('path')
        if not path:
            return True
        try:
            res = DataLakeResource.objects.get(path=path)
        except DataLakeResource.DoesNotExist:
            return False
        needed = 'read' if request.method in ('GET','HEAD','OPTIONS') else 'write'
        return PermissionEntry.objects.filter(user=request.user, resource=res, access=needed).exists()
