from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    Company, CustomUser, CTOMapFile, Ticket, TicketMessage, TicketNotification,
    ConsentRecord,
    DataSubjectRequest,
    LgpdExportDownload,
    AccountActivationToken,
    SecurityAuditEvent,
    CompanyBilling,
)

class RMOnlyAdminSite(AdminSite):
    site_header = "RM Systems Admin"
    site_title = "RM Admin"
    index_title = "Painel RM"

    def has_permission(self, request):
        user = request.user
        # Permite acesso para superusuários OU usuários ativos, staff e com role RM
        if user.is_superuser:
            return True
        # Permite acesso somente para usuários ativos, staff e com role RM
        return user.is_active and user.is_staff and getattr(user, 'role', None) == 'RM'

# Instância do AdminSite restrita a RM
rm_admin_site = RMOnlyAdminSite(name='rm_admin')

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'plan_code', 'cnpj_masked_display', 'email', 'is_active', 'quota_enforcement', 'created_at']
    list_filter = ['is_active', 'plan_code', 'quota_enforcement', 'created_at']
    search_fields = ['name', 'cnpj_hash', 'email']
    readonly_fields = ['created_at', 'updated_at', 'cnpj_hash', 'cnpj_masked_display']

    def cnpj_masked_display(self, obj):
        return obj.cnpj_masked
    cnpj_masked_display.short_description = 'CNPJ'

    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'cnpj', 'cnpj_masked_display', 'cnpj_hash', 'email', 'phone')
        }),
        ('Endereço', {
            'fields': ('address',)
        }),
        ('Plano e limites', {
            'fields': (
                'plan_code',
                'quota_enforcement',
                'quota_override_users',
                'quota_override_maps',
                'quota_override_viability_month',
                'quota_override_whatsapp_chips',
                'quota_override_alert_phones',
                'quota_override_alert_messages_month',
                'quota_override_olts',
                'quota_override_olt_jobs_month',
            ),
        }),
        ('Módulos da plataforma', {
            'fields': ('module_verificador', 'module_alertas', 'module_olt'),
            'description': 'Ao salvar pelo formulário RM, o plano pode redefinir os módulos automaticamente.',
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'company', 'is_active']
    list_filter = ['role', 'company', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Informações Customizadas', {
            'fields': ('role', 'company', 'phone')
        }),
        ('Datas Customizadas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.is_rm_admin:
            return qs
        elif request.user.is_company_admin:
            return qs.filter(company=request.user.company)
        return qs.none()

@admin.register(CTOMapFile)
class CTOMapFileAdmin(admin.ModelAdmin):
    list_display = ['file', 'company', 'uploaded_by', 'uploaded_at', 'is_processed']
    list_filter = ['company', 'is_processed', 'uploaded_at']
    search_fields = ['file', 'description', 'company__name', 'uploaded_by__username']
    readonly_fields = ['uploaded_at', 'processed_at']
    
    fieldsets = (
        ('Arquivo', {
            'fields': ('file', 'description')
        }),
        ('Associações', {
            'fields': ('company', 'uploaded_by')
        }),
        ('Status', {
            'fields': ('is_processed', 'processed_at')
        }),
        ('Datas', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.is_rm_admin:
            return qs
        elif request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        if not change:  # Se é um novo objeto
            if not obj.uploaded_by:
                obj.uploaded_by = request.user
            if not obj.company and request.user.company:
                obj.company = request.user.company
        super().save_model(request, obj, form, change)

class TicketMessageInline(admin.TabularInline):
    """Inline para exibir mensagens do ticket"""
    model = TicketMessage
    extra = 0
    readonly_fields = ['sent_by', 'created_at', 'read', 'read_at']
    fields = ['message', 'sent_by', 'created_at', 'read', 'read_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 
        'title_short', 
        'company', 
        'created_by', 
        'status_badge', 
        'priority_badge',
        'assigned_to',
        'messages_count',
        'created_at',
        'actions_links'
    ]
    list_filter = [
        'status',
        'priority',
        'company',
        'created_at',
        'resolved_at',
        'closed_at'
    ]
    search_fields = [
        'ticket_number',
        'title',
        'description',
        'company__name',
        'created_by__username',
        'created_by__email',
        'assigned_to__username'
    ]
    readonly_fields = [
        'ticket_number',
        'created_at',
        'updated_at',
        'resolved_at',
        'closed_at',
        'messages_count_display'
    ]
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('ticket_number', 'title', 'description')
        }),
        ('Status e Prioridade', {
            'fields': ('status', 'priority')
        }),
        ('Associações', {
            'fields': ('company', 'created_by', 'assigned_to')
        }),
        ('Estatísticas', {
            'fields': ('messages_count_display',),
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at', 'resolved_at', 'closed_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TicketMessageInline]
    
    actions = [
        'marcar_como_em_andamento',
        'marcar_como_resolvido',
        'marcar_como_fechado',
        'marcar_prioridade_alta',
        'marcar_prioridade_urgente'
    ]
    
    def title_short(self, obj):
        """Exibe título truncado"""
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Título'
    
    def status_badge(self, obj):
        """Exibe status com cor"""
        colors = {
            'aberto': '#007bff',
            'em_andamento': '#ffc107',
            'aguardando_cliente': '#fd7e14',
            'resolvido': '#28a745',
            'fechado': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def priority_badge(self, obj):
        """Exibe prioridade com cor"""
        colors = {
            'baixa': '#6c757d',
            'normal': '#007bff',
            'alta': '#ffc107',
            'urgente': '#dc3545',
        }
        color = colors.get(obj.priority, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Prioridade'
    priority_badge.admin_order_field = 'priority'
    
    def messages_count(self, obj):
        """Exibe quantidade de mensagens"""
        count = obj.messages.count()
        if count > 0:
            return format_html(
                '<span style="background-color: #17a2b8; color: white; padding: 3px 8px; '
                'border-radius: 10px; font-weight: bold;">{}</span>',
                count
            )
        return '0'
    messages_count.short_description = 'Mensagens'
    messages_count.admin_order_field = 'messages__count'
    
    def messages_count_display(self, obj):
        """Exibe quantidade de mensagens no formulário"""
        if obj.pk:
            count = obj.messages.count()
            return format_html('<strong>{} mensagem(ns)</strong>', count)
        return 'N/A (ticket ainda não salvo)'
    messages_count_display.short_description = 'Total de Mensagens'
    
    def actions_links(self, obj):
        """Links para ações rápidas"""
        if not obj.pk:
            return '-'
        
        links = []
        detail_url = reverse('admin:core_ticket_change', args=[obj.pk])
        links.append(format_html('<a href="{}">Ver</a>', detail_url))
        
        if obj.status != 'fechado':
            if obj.status != 'resolvido':
                resolve_url = reverse('admin:core_ticket_change', args=[obj.pk])
                links.append(format_html(
                    '<a href="{}?resolve=1" style="color: #28a745; margin-left: 10px;">✓ Resolver</a>',
                    resolve_url
                ))
            close_url = reverse('admin:core_ticket_change', args=[obj.pk])
            links.append(format_html(
                '<a href="{}?close=1" style="color: #dc3545; margin-left: 10px;">✗ Fechar</a>',
                close_url
            ))
        
        return format_html(' | '.join(links))
    actions_links.short_description = 'Ações'
    
    def marcar_como_em_andamento(self, request, queryset):
        """Ação para marcar tickets como em andamento"""
        updated = queryset.exclude(status='fechado').update(status='em_andamento')
        self.message_user(request, f'{updated} ticket(s) marcado(s) como em andamento.')
    marcar_como_em_andamento.short_description = 'Marcar como Em Andamento'
    
    def marcar_como_resolvido(self, request, queryset):
        """Ação para marcar tickets como resolvido"""
        updated = queryset.exclude(status='fechado').update(
            status='resolvido',
            resolved_at=timezone.now()
        )
        self.message_user(request, f'{updated} ticket(s) marcado(s) como resolvido(s).')
    marcar_como_resolvido.short_description = 'Marcar como Resolvido'
    
    def marcar_como_fechado(self, request, queryset):
        """Ação para fechar tickets"""
        updated = queryset.exclude(status='fechado').update(
            status='fechado',
            closed_at=timezone.now()
        )
        self.message_user(request, f'{updated} ticket(s) fechado(s).')
    marcar_como_fechado.short_description = 'Fechar Tickets'
    
    def marcar_prioridade_alta(self, request, queryset):
        """Ação para marcar prioridade como alta"""
        updated = queryset.update(priority='alta')
        self.message_user(request, f'{updated} ticket(s) com prioridade alta.')
    marcar_prioridade_alta.short_description = 'Marcar Prioridade como Alta'
    
    def marcar_prioridade_urgente(self, request, queryset):
        """Ação para marcar prioridade como urgente"""
        updated = queryset.update(priority='urgente')
        self.message_user(request, f'{updated} ticket(s) com prioridade urgente.')
    marcar_prioridade_urgente.short_description = 'Marcar Prioridade como Urgente'
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Intercepta mudanças de status via GET parameters"""
        if object_id and request.method == 'GET':
            if 'resolve' in request.GET:
                try:
                    ticket = Ticket.objects.get(pk=object_id)
                    if ticket.status != 'fechado':
                        ticket.status = 'resolvido'
                        ticket.resolved_at = timezone.now()
                        ticket.save()
                        self.message_user(request, f'Ticket {ticket.ticket_number} marcado como resolvido.')
                except Ticket.DoesNotExist:
                    pass
            elif 'close' in request.GET:
                try:
                    ticket = Ticket.objects.get(pk=object_id)
                    if ticket.status != 'fechado':
                        ticket.status = 'fechado'
                        ticket.closed_at = timezone.now()
                        ticket.save()
                        self.message_user(request, f'Ticket {ticket.ticket_number} fechado.')
                except Ticket.DoesNotExist:
                    pass
        
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    def get_queryset(self, request):
        """Filtrar queryset baseado nas permissões"""
        qs = super().get_queryset(request)
        qs = qs.select_related('company', 'created_by', 'assigned_to')
        qs = qs.prefetch_related('messages')
        
        if request.user.is_superuser or request.user.is_rm_admin:
            return qs
        elif request.user.company:
            # Company admin vê apenas tickets da sua empresa
            return qs.filter(company=request.user.company)
        return qs.none()

@admin.register(TicketMessage)


class TicketMessageAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'ticket_link',
        'message_short',
        'sent_by',
        'read_badge',
        'created_at'
    ]
    list_filter = [
        'read',
        'created_at',
        'ticket__status',
        'ticket__company'
    ]
    search_fields = [
        'message',
        'ticket__ticket_number',
        'ticket__title',
        'sent_by__username',
        'sent_by__email'
    ]
    readonly_fields = ['created_at', 'read_at']
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    fieldsets = (
        ('Mensagem', {
            'fields': ('ticket', 'message', 'sent_by')
        }),
        ('Status de Leitura', {
            'fields': ('read', 'read_at')
        }),
        ('Data', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def ticket_link(self, obj):
        """Link para o ticket"""
        if obj.ticket:
            url = reverse('admin:core_ticket_change', args=[obj.ticket.pk])
            return format_html('<a href="{}">{}</a>', url, obj.ticket.ticket_number)
        return '-'
    ticket_link.short_description = 'Ticket'
    ticket_link.admin_order_field = 'ticket__ticket_number'
    
    def message_short(self, obj):
        """Exibe mensagem truncada"""
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_short.short_description = 'Mensagem'
    
    def read_badge(self, obj):
        """Exibe status de leitura"""
        if obj.read:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px;">Lida</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
            'border-radius: 3px;">Não Lida</span>'
        )
    read_badge.short_description = 'Status'
    read_badge.admin_order_field = 'read'
    
    def get_queryset(self, request):
        """Filtrar queryset baseado nas permissões"""
        qs = super().get_queryset(request)
        qs = qs.select_related('ticket', 'sent_by', 'ticket__company')
        
        if request.user.is_superuser or request.user.is_rm_admin:
            return qs
        elif request.user.company:
            # Company admin vê apenas mensagens de tickets da sua empresa
            return qs.filter(ticket__company=request.user.company)
        return qs.none()

# Registrar modelos também no AdminSite restrito a RM
rm_admin_site.register(Company, CompanyAdmin)
rm_admin_site.register(CustomUser, CustomUserAdmin)
rm_admin_site.register(CTOMapFile, CTOMapFileAdmin)
rm_admin_site.register(Ticket, TicketAdmin)
rm_admin_site.register(TicketMessage, TicketMessageAdmin)


@admin.register(TicketNotification)
class TicketNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'notification_type', 'recipient', 'read', 'created_at')
    list_filter = ('notification_type', 'read', 'created_at')
    search_fields = ('ticket__ticket_number', 'recipient__username', 'message')
    readonly_fields = ('created_at', 'read_at')
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('ticket', 'recipient', 'created_by')

rm_admin_site.register(TicketNotification, TicketNotificationAdmin)


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "document_type", "document_version", "accepted_at", "ip_address")
    list_filter = ("document_type", "document_version", "accepted_at")
    search_fields = ("user__username", "user__email", "ip_address")
    readonly_fields = ("accepted_at",)
    date_hierarchy = "accepted_at"


@admin.register(DataSubjectRequest)
class DataSubjectRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "request_type", "status", "retry_count", "created_at", "completed_at")
    list_filter = ("request_type", "status", "created_at")
    search_fields = ("user__username", "user__email", "details")
    readonly_fields = ("created_at",)
    actions = ["mark_completed"]

    @admin.action(description="Marcar como concluída")
    def mark_completed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status="completed", completed_at=timezone.now())


rm_admin_site.register(ConsentRecord, ConsentRecordAdmin)
rm_admin_site.register(DataSubjectRequest, DataSubjectRequestAdmin)


@admin.register(LgpdExportDownload)
class LgpdExportDownloadAdmin(admin.ModelAdmin):
    list_display = ("user", "export_format", "expires_at", "download_count", "created_at")
    list_filter = ("export_format", "expires_at")
    readonly_fields = ("checksum_sha256", "storage_path", "created_at", "last_downloaded_at")


@admin.register(AccountActivationToken)
class AccountActivationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at", "created_ip")
    list_filter = ("used_at", "expires_at")
    search_fields = ("user__username", "user__email", "token_digest")
    readonly_fields = ("token_digest", "django_token", "created_at", "expires_at", "used_at", "created_ip", "used_ip")

    def has_add_permission(self, request):
        return False


rm_admin_site.register(AccountActivationToken, AccountActivationTokenAdmin)


@admin.register(SecurityAuditEvent)
class SecurityAuditEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "severity", "user", "ip_address", "request_id", "created_at")
    list_filter = ("event_type", "severity", "created_at")
    search_fields = ("event_type", "request_id", "correlation_id", "user__username")
    readonly_fields = ("created_at", "details")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


rm_admin_site.register(SecurityAuditEvent, SecurityAuditEventAdmin)


class CompanyBillingAdmin(admin.ModelAdmin):
    list_display = ("company", "provider", "status", "last_payment_at", "last_webhook_at")
    list_filter = ("provider", "status")
    search_fields = ("company__name", "asaas_customer_id", "asaas_subscription_id")
    readonly_fields = ("created_at", "updated_at", "last_webhook_at", "last_webhook_event")


rm_admin_site.register(CompanyBilling, CompanyBillingAdmin)
