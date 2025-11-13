from rest_framework import serializers
from .models import DataLakeResource, PermissionEntry, AuditLog, VersionEntry
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username','email']

class DataLakeResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataLakeResource
        fields = '__all__'

class PermissionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = PermissionEntry
        fields = '__all__'

class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = AuditLog
        fields = '__all__'
