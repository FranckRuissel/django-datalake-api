from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class DataLakeResource(models.Model):
    path = models.CharField(max_length=1024, unique=True)
    is_folder = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.path

class PermissionEntry(models.Model):
    READ = 'read'
    WRITE = 'write'
    ROLES = [(READ, 'Read'), (WRITE, 'Write')]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    resource = models.ForeignKey(DataLakeResource, on_delete=models.CASCADE)
    access = models.CharField(max_length=10, choices=ROLES)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user','resource','access')

class AuditLog(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    path = models.CharField(max_length=1024)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField(null=True)
    request_body = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

class VersionEntry(models.Model):
    resource = models.ForeignKey(DataLakeResource, on_delete=models.CASCADE)
    version_tag = models.CharField(max_length=128)
    file_path = models.CharField(max_length=1024)
    created_at = models.DateTimeField(auto_now_add=True)
