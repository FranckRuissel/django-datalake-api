from django.contrib import admin
from .models import DataLakeResource, PermissionEntry, AuditLog, VersionEntry

admin.site.register(DataLakeResource)
admin.site.register(PermissionEntry)
admin.site.register(AuditLog)
admin.site.register(VersionEntry)
