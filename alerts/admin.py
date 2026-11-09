from django.contrib import admin
from .models import AlertBridgeConfig, WhatsAppLine


@admin.register(AlertBridgeConfig)
class AlertBridgeConfigAdmin(admin.ModelAdmin):
    list_display = ["company", "is_active", "telegram_group_id", "updated_at"]
    list_filter = ["is_active", "filter_enabled"]
    search_fields = ["company__name", "telegram_group_id"]
    raw_id_fields = ["company"]


@admin.register(WhatsAppLine)
class WhatsAppLineAdmin(admin.ModelAdmin):
    list_display = ["label", "company", "login_mode", "is_active", "send_alerts", "is_default"]
    list_filter = ["is_active", "login_mode", "company"]
    search_fields = ["label", "company__name"]
