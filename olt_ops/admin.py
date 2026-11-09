from django.contrib import admin
from .models import CompanyOltExecutionConfig, CompanyVpnConfig, OltEquipment, OnuCleanupJob


@admin.register(CompanyOltExecutionConfig)
class CompanyOltExecutionConfigAdmin(admin.ModelAdmin):
    list_display = ["company", "worker_mode", "max_concurrent_jobs", "updated_at"]
    list_filter = ["worker_mode"]
    search_fields = ["company__name"]


@admin.register(CompanyVpnConfig)
class CompanyVpnConfigAdmin(admin.ModelAdmin):
    list_display = ["company", "name", "is_enabled", "vpn_type", "ipsec_server", "updated_at"]
    list_filter = ["is_enabled", "vpn_type"]
    search_fields = ["company__name", "name", "ipsec_server"]
    fieldsets = (
        (None, {"fields": ("company", "is_enabled", "name", "vpn_type")}),
        ("L2TP/IPsec", {"fields": ("ipsec_server", "ipsec_psk", "vpn_username", "vpn_password")}),
        ("OpenVPN", {"fields": ("ovpn_content",)}),
        ("Outros", {"fields": ("notes",)}),
    )


@admin.register(OltEquipment)
class OltEquipmentAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "host", "vendor", "is_active"]
    list_filter = ["vendor", "protocol", "is_active"]
    search_fields = ["name", "host", "company__name"]


@admin.register(OnuCleanupJob)
class OnuCleanupJobAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "olt", "gpon_port", "status", "created_at"]
    list_filter = ["status"]
    raw_id_fields = ["company", "olt", "created_by"]
