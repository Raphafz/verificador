"""
Serializers para API REST
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Company, CTOMapFile
from .permissions import is_rm_admin

User = get_user_model()

class CompanySerializer(serializers.ModelSerializer):
    """Serializer para Company — CNPJ nunca exposto em claro na API."""
    user_count = serializers.SerializerMethodField()
    map_count = serializers.SerializerMethodField()
    cnpj_masked = serializers.CharField(read_only=True)

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'slug', 'email', 'phone', 'address',
            'cnpj_masked', 'created_at', 'user_count', 'map_count',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'cnpj_masked']
    
    def get_user_count(self, obj):
        return obj.users.count()

    def get_map_count(self, obj):
        return obj.cto_maps.count()

class UserSerializer(serializers.ModelSerializer):
    """Serializer para User"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'phone', 'role', 'is_active', 'company',
            'company_name', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'company']

    def validate_role(self, value):
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        if actor and is_rm_admin(actor):
            return value
        if value == "RM":
            raise serializers.ValidationError("Não é permitido atribuir função RM.")
        if self.instance:
            if value != self.instance.role:
                raise serializers.ValidationError(
                    "Alteração de função não permitida pela API."
                )
        elif value != "COMPANY_USER":
            raise serializers.ValidationError(
                "Criação via API permitida apenas para usuários COMPANY_USER."
            )
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        actor = getattr(request, "user", None) if request else None
        if actor and not is_rm_admin(actor):
            attrs.pop("company", None)
            if self.instance and self.instance.pk == actor.pk:
                if "role" in attrs and attrs["role"] != self.instance.role:
                    raise serializers.ValidationError(
                        {"role": "Você não pode alterar sua própria função."}
                    )
                if "is_active" in attrs and attrs["is_active"] is False:
                    raise serializers.ValidationError(
                        {"is_active": "Você não pode desativar sua própria conta."}
                    )
        return attrs
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

class CTOMapFileSerializer(serializers.ModelSerializer):
    """Serializer para CTOMapFile"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()
    original_filename = serializers.SerializerMethodField()
    
    class Meta:
        model = CTOMapFile
        fields = [
            'id', 'original_filename', 'description', 'file_type', 'file_size',
            'file_size_mb', 'uploaded_at', 'company', 'company_name',
            'uploaded_by', 'uploaded_by_name', 'processing_status', 'is_processed',
        ]
        read_only_fields = [
            'id', 'uploaded_at', 'company', 'uploaded_by', 'file_size',
            'processing_status', 'is_processed',
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        actor = getattr(request, "user", None) if request else None
        if actor and not is_rm_admin(actor):
            attrs.pop("company", None)
        return attrs
    
    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name()
        return ''

    def get_original_filename(self, obj):
        if obj.file and obj.file.name:
            import os
            return os.path.basename(obj.file.name)
        return obj.description or ''
    
    def get_file_size_mb(self, obj):
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return 0

class CompanyStatsSerializer(serializers.Serializer):
    """Serializer para estatísticas de empresa"""
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    total_maps = serializers.IntegerField()
    maps_this_month = serializers.IntegerField()
    last_activity = serializers.DateTimeField(allow_null=True)

class MapStatsSerializer(serializers.Serializer):
    """Serializer para estatísticas de mapas"""
    total = serializers.IntegerField()
    this_month = serializers.IntegerField()
    this_week = serializers.IntegerField()
    by_type = serializers.ListField()

class UserStatsSerializer(serializers.Serializer):
    """Serializer para estatísticas de usuários"""
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    inactive = serializers.IntegerField()
    by_role = serializers.ListField()
    recent_registrations = serializers.IntegerField()
