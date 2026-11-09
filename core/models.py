from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils import timezone
import os

from .encrypted_fields import EncryptedCharField
from .cnpj_utils import format_cnpj, hash_cnpj, mask_cnpj_display

class Company(models.Model):
    """Modelo para representar as empresas clientes"""
    name = models.CharField(max_length=200, verbose_name="Nome da Empresa")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="Slug", help_text="URL amigável para a empresa")
    cnpj = EncryptedCharField(max_length=512, verbose_name="CNPJ")
    cnpj_hash = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        editable=False,
        verbose_name="Hash CNPJ (busca)",
    )
    email = models.EmailField(verbose_name="E-mail da Empresa")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefone")
    address = models.TextField(blank=True, verbose_name="Endereço")
    is_active = models.BooleanField(default=True, verbose_name="Ativa")
    module_verificador = models.BooleanField(
        default=True,
        verbose_name="Módulo Verificador FTTH",
        help_text="Mapas CTO e verificação de viabilidade",
    )
    module_alertas = models.BooleanField(
        default=False,
        verbose_name="Módulo Alertas",
        help_text="Bridge Telegram → WhatsApp para monitoramento",
    )
    module_olt = models.BooleanField(
        default=False,
        verbose_name="Módulo OLT/ONU",
        help_text="Gestão de ONTs offline em OLT Huawei/ZTE",
    )
    plan_code = models.CharField(
        max_length=4,
        choices=[
            ("P", "P — Essencial"),
            ("M", "M — Comercial"),
            ("G", "G — Operação"),
            ("XL", "XL — Rede"),
        ],
        default="M",
        verbose_name="Plano comercial",
        help_text="Define limites de usuários, mapas, viabilidade e módulos.",
    )
    quota_enforcement = models.BooleanField(
        default=True,
        verbose_name="Aplicar limites do plano",
        help_text="Desmarque apenas para acordos especiais (RM).",
    )
    quota_override_users = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Override: usuários",
    )
    quota_override_maps = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Override: mapas",
    )
    quota_override_viability_month = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Override: consultas viabilidade/mês",
    )
    quota_override_whatsapp_chips = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Override: chips WhatsApp",
    )
    quota_override_alert_phones = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Override: números de alerta",
    )
    quota_override_alert_messages_month = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Override: mensagens alerta/mês",
    )
    quota_override_olts = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Override: OLTs",
    )
    quota_override_olt_jobs_month = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Override: jobs ONU/mês",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizada em")

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'name']),
            models.Index(fields=['cnpj_hash']),
        ]

    def enabled_modules(self):
        """Lista de códigos dos módulos ativos desta empresa."""
        modules = []
        if self.module_verificador:
            modules.append("verificador")
        if self.module_alertas:
            modules.append("alertas")
        if self.module_olt:
            modules.append("olt")
        return modules

    def has_module(self, code):
        return code in self.enabled_modules()

    def get_plan_limits(self):
        from core.quotas import resolve_limits

        return resolve_limits(self)

    def get_usage_summary(self):
        from core.quotas import get_usage_summary

        return get_usage_summary(self)

    def save(self, *args, **kwargs):
        if self.cnpj:
            from .cnpj_utils import cnpj_digits
            digits = cnpj_digits(self.cnpj)
            if len(digits) == 14:
                self.cnpj = format_cnpj(digits)
                self.cnpj_hash = hash_cnpj(digits)
        if not self.slug:
            self.slug = slugify(self.name)
            original_slug = self.slug
            counter = 1
            while Company.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def cnpj_masked(self) -> str:
        return mask_cnpj_display(self.cnpj)

    def __str__(self):
        return self.name


class CompanyBilling(models.Model):
    """Assinatura / cobrança recorrente (Asaas ou manual)."""

    PROVIDER_CHOICES = [
        ("manual", "Manual (RM)"),
        ("asaas", "Asaas"),
    ]
    STATUS_CHOICES = [
        ("trial", "Trial"),
        ("active", "Ativa"),
        ("past_due", "Inadimplente"),
        ("suspended", "Suspensa"),
        ("cancelled", "Cancelada"),
    ]

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="billing",
        verbose_name="Empresa",
    )
    provider = models.CharField(
        max_length=16,
        choices=PROVIDER_CHOICES,
        default="manual",
        verbose_name="Provedor",
    )
    asaas_customer_id = models.CharField(max_length=64, blank=True, verbose_name="ID cliente Asaas")
    asaas_subscription_id = models.CharField(
        max_length=64, blank=True, verbose_name="ID assinatura Asaas"
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="trial",
        verbose_name="Status cobrança",
    )
    last_payment_at = models.DateTimeField(null=True, blank=True, verbose_name="Último pagamento")
    last_webhook_at = models.DateTimeField(null=True, blank=True, verbose_name="Último webhook")
    last_webhook_event = models.CharField(max_length=64, blank=True, verbose_name="Último evento")
    notes = models.TextField(blank=True, verbose_name="Observações RM")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cobrança da empresa"
        verbose_name_plural = "Cobranças das empresas"

    def __str__(self):
        return f"Cobrança — {self.company.name} ({self.get_status_display()})"

    def apply_payment_received(self) -> None:
        self.status = "active"
        self.last_payment_at = timezone.now()
        self.save(update_fields=["status", "last_payment_at", "updated_at"])
        if not self.company.is_active:
            self.company.is_active = True
            self.company.save(update_fields=["is_active", "updated_at"])

    def apply_payment_overdue(self) -> None:
        self.status = "past_due"
        self.save(update_fields=["status", "updated_at"])

    def apply_subscription_cancelled(self) -> None:
        self.status = "cancelled"
        self.save(update_fields=["status", "updated_at"])
        self.company.is_active = False
        self.company.save(update_fields=["is_active", "updated_at"])


class CustomUser(AbstractUser):
    """Modelo customizado de usuário com roles e empresa"""
    
    USER_ROLES = [
        ('RM', 'Administrador RM'),  # Você e o Bone
        ('COMPANY_ADMIN', 'Administrador da Empresa'),  # Admin da empresa cliente
        ('COMPANY_USER', 'Usuário da Empresa'),  # Usuário comum da empresa
    ]
    
    role = models.CharField(
        max_length=20, 
        choices=USER_ROLES, 
        default='COMPANY_USER',
        verbose_name="Função"
    )
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='users',
        verbose_name="Empresa",
        db_index=True
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefone")
    must_change_password = models.BooleanField(
        default=True,
        verbose_name="Deve mudar senha",
        help_text="Força a mudança de senha no primeiro acesso"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em", db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        indexes = [
            models.Index(fields=['company', 'role']),
            models.Index(fields=['username']),
            models.Index(fields=['email']),
        ]

    def clean(self):
        """Validações customizadas"""
        super().clean()
        
        # Superusuários não precisam seguir as regras de empresa
        if self.is_superuser:
            return
        
        # NOTA: Validações de empresa/role são feitas no formulário
        # O modelo apenas ajusta os dados no save() para garantir consistência
        # Não lançar ValidationError aqui para evitar conflitos com o formulário
        
    def save(self, *args, **kwargs):
        # Ajustar dados antes de validar
        # IMPORTANTE: Superusuários sempre mantêm seus privilégios, independente do role
        if self.is_superuser:
            # Superusuários podem ter qualquer role e manter is_superuser=True
            # Não remover is_superuser nem is_staff de superusuários
            if self.role == 'RM':
                # RM não deve ter empresa associada
                self.company_id = None
                # RM pode acessar áreas administrativas do sistema
                if not self.is_staff:
                    self.is_staff = True
        elif self.role == 'RM':
            # RM não deve ter empresa associada
            self.company_id = None
            # RM pode acessar áreas administrativas do sistema
            if not self.is_staff:
                self.is_staff = True
            # Não forçamos superuser aqui; fica a cargo de seed/gestão
        else:
            # Usuários de empresas nunca devem ser superuser, nem staff global
            # Mas apenas se não forem superusuários (já verificado acima)
            if not self.is_superuser:
                # Apenas remover is_staff se não for superuser
                if self.is_staff:
                    self.is_staff = False
        
        # Não chamar clean() aqui para evitar validações que já foram feitas no formulário
        # O formulário já validou role/company, então apenas salvar
        # Se houver erro de validação básica do Django (email único, etc.), deixar passar
        super().save(*args, **kwargs)

    @property
    def is_rm_admin(self):
        """Verifica se é administrador RM"""
        return self.role == 'RM' or self.is_superuser

    @property
    def is_company_admin(self):
        """Verifica se é administrador da empresa"""
        return self.role == 'COMPANY_ADMIN'

    @property
    def can_manage_users(self):
        """Verifica se pode gerenciar usuários"""
        return self.is_rm_admin or self.is_company_admin

    @property
    def can_upload_maps(self):
        """Verifica se pode fazer upload de mapas"""
        return self.is_rm_admin or self.role in ['COMPANY_ADMIN', 'COMPANY_USER']

    def get_full_name(self):
        """Retorna nome completo ou username"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    def __str__(self):
        if self.company:
            return f"{self.get_full_name() or self.username} - {self.company.name}"
        return self.get_full_name() or self.username

class CTOMapFile(models.Model):
    """Modelo para arquivos de mapas CTO"""
    
    FILE_TYPES = [
        ('kml', 'KML'),
        ('kmz', 'KMZ'),
        ('csv', 'CSV'),
        ('xls', 'XLS'),
        ('xlsx', 'XLSX'),
    ]
    
    PROCESSING_STATUS = [
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('completed', 'Concluído'),
        ('failed', 'Falhou'),
    ]
    
    file = models.FileField(
        upload_to="core.upload_security.secure_cto_upload_path",
        verbose_name="Arquivo",
    )
    description = models.CharField(max_length=255, blank=True, verbose_name="Descrição")
    file_type = models.CharField(max_length=10, choices=FILE_TYPES, default='csv', verbose_name="Tipo de Arquivo")
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE,
        related_name='cto_maps',
        verbose_name="Empresa",
        db_index=True
    )
    uploaded_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='uploaded_maps',
        verbose_name="Enviado por",
        db_index=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Enviado em", db_index=True)
    
    # Status de processamento
    processing_status = models.CharField(
        max_length=20, 
        choices=PROCESSING_STATUS, 
        default='pending',
        verbose_name="Status de Processamento"
    )
    is_processed = models.BooleanField(default=False, verbose_name="Processado")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Processado em")
    
    # Resultados da análise Flask
    analysis_id = models.CharField(max_length=100, blank=True, verbose_name="ID da Análise")
    viability_score = models.IntegerField(null=True, blank=True, verbose_name="Score de Viabilidade")
    processing_time = models.FloatField(null=True, blank=True, verbose_name="Tempo de Processamento (s)")
    
    # Dados da análise (JSON)
    analysis_results = models.JSONField(default=dict, blank=True, verbose_name="Resultados da Análise")
    issues_found = models.JSONField(default=list, blank=True, verbose_name="Problemas Encontrados")
    recommendations = models.JSONField(default=list, blank=True, verbose_name="Recomendações")
    
    # Metadados do arquivo
    file_size = models.BigIntegerField(null=True, blank=True, verbose_name="Tamanho do Arquivo (bytes)")
    coordinates_count = models.IntegerField(null=True, blank=True, verbose_name="Número de Coordenadas")
    
    # Campos de auditoria
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Mapa CTO"
        verbose_name_plural = "Mapas CTO"
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['company', 'processing_status']),
            models.Index(fields=['uploaded_by', 'uploaded_at']),
            models.Index(fields=['file_type', 'is_processed']),
        ]

    def clean(self):
        """Validações customizadas"""
        super().clean()
        
        # Verificar se o usuário pode fazer upload (exceto RM Admins e superusers)
        if self.uploaded_by:
            is_rm_admin = getattr(self.uploaded_by, 'is_rm_admin', False)
            is_superuser = getattr(self.uploaded_by, 'is_superuser', False)
            is_company_admin = getattr(self.uploaded_by, 'is_company_admin', False)
            
            # RM Admins, superusers e Company Admins sempre podem fazer upload
            if not (is_rm_admin or is_superuser or is_company_admin):
                if not self.uploaded_by.can_upload_maps:
                    raise ValidationError("Usuário não tem permissão para fazer upload de mapas.")
        
        # Verificar se o usuário pertence à empresa (exceto RM Admins e superusers)
        if self.uploaded_by and self.company:
            is_rm_admin = getattr(self.uploaded_by, 'is_rm_admin', False)
            is_superuser = getattr(self.uploaded_by, 'is_superuser', False)
            
            # RM Admins e superusers podem fazer upload para qualquer empresa
            if not (is_rm_admin or is_superuser):
                if not self.uploaded_by.company or self.uploaded_by.company != self.company:
                    raise ValidationError("Usuário não pertence à empresa especificada.")
        
        # Determinar tipo de arquivo automaticamente baseado no nome do arquivo
        # Sempre detectar baseado no nome real, mesmo se file_type já estiver definido
        if self.file:
            file_name = self.file.name.lower()
            # Detectar extensão do arquivo
            if file_name.endswith('.kml'):
                self.file_type = 'kml'
            elif file_name.endswith('.kmz'):
                self.file_type = 'kmz'
            elif file_name.endswith('.csv'):
                self.file_type = 'csv'
            elif file_name.endswith('.xls'):
                self.file_type = 'xls'
            elif file_name.endswith('.xlsx'):
                self.file_type = 'xlsx'
            # Se não detectou nenhuma extensão conhecida e file_type está vazio, usar default
            elif not self.file_type:
                self.file_type = 'csv'  # Fallback para o default
    
    def save(self, *args, **kwargs):
        self.clean()
        
        # Calcular tamanho do arquivo
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except (OSError, ValueError):
                pass
        
        super().save(*args, **kwargs)
    
    def get_file_size_mb(self):
        """Retorna o tamanho do arquivo em MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0
    
    def get_viability_status(self):
        """Retorna o status de viabilidade baseado no score"""
        if self.viability_score is None:
            return "Não analisado"
        
        if self.viability_score >= 80:
            return "Viável"
        elif self.viability_score >= 60:
            return "Viabilidade Limitada"
        else:
            return "Sem Viabilidade"
    
    def get_viability_color(self):
        """Retorna a cor do status de viabilidade"""
        if self.viability_score is None:
            return "#6c757d"  # Cinza
        
        if self.viability_score >= 80:
            return "#28a745"  # Verde
        elif self.viability_score >= 60:
            return "#ffc107"  # Amarelo
        else:
            return "#dc3545"  # Vermelho
    
    @property
    def file_name(self):
        """Retorna apenas o nome do arquivo"""
        return os.path.basename(self.file.name) if self.file else ""

    def __str__(self):
        return f"{self.description or os.path.basename(self.file.name)} - {self.company.name}"


class Ticket(models.Model):
    """Modelo para tickets de suporte"""
    
    STATUS_CHOICES = [
        ('aberto', 'Aberto'),
        ('em_andamento', 'Em Andamento'),
        ('aguardando_cliente', 'Aguardando Cliente'),
        ('resolvido', 'Resolvido'),
        ('fechado', 'Fechado'),
    ]
    
    PRIORITY_CHOICES = [
        ('baixa', 'Baixa'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    title = models.CharField(max_length=255, verbose_name="Título")
    description = models.TextField(verbose_name="Descrição")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='aberto',
        verbose_name="Status"
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='normal',
        verbose_name="Prioridade"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name="Empresa"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='created_tickets',
        verbose_name="Criado por"
    )
    assigned_to = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        verbose_name="Atendido por"
    )
    ticket_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Número do Ticket",
        help_text="Gerado automaticamente"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Resolvido em")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Fechado em")
    
    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['created_by', 'created_at']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['ticket_number']),
        ]
    
    def save(self, *args, **kwargs):
        from django.utils import timezone
        import time
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Gerar número do ticket se não existir - usar abordagem mais simples
        if not self.ticket_number:
            prefix = "TKT"
            timestamp = timezone.now().strftime("%Y%m%d")
            
            # Usar timestamp com microsegundos para garantir unicidade
            # Isso evita queries complexas que podem falhar
            unique_suffix = str(int(time.time() * 1000000))[-6:]  # Últimos 6 dígitos do microsegundo
            self.ticket_number = f"{prefix}-{timestamp}-{unique_suffix}"
            
            # Verificar se já existe (improvável, mas seguro)
            max_attempts = 5
            attempt = 0
            while attempt < max_attempts:
                try:
                    if self.pk:
                        exists = Ticket.objects.filter(ticket_number=self.ticket_number).exclude(pk=self.pk).exists()
                    else:
                        exists = Ticket.objects.filter(ticket_number=self.ticket_number).exists()
                    
                    if not exists:
                        break
                    else:
                        # Se existe, adicionar um dígito extra
                        unique_suffix = str(int(time.time() * 1000000))[-6:] + str(attempt)
                        self.ticket_number = f"{prefix}-{timestamp}-{unique_suffix}"
                except Exception as e:
                    logger.warning(f"Erro ao verificar ticket_number: {str(e)}")
                    break
                
                attempt += 1
        
        # Atualizar timestamps baseado no status
        if self.status == 'resolvido' and not self.resolved_at:
            self.resolved_at = timezone.now()
        
        if self.status == 'fechado' and not self.closed_at:
            self.closed_at = timezone.now()
        
        try:
            super().save(*args, **kwargs)
        except Exception as e:
            # Log do erro antes de relançar
            logger.exception(f"Erro ao salvar ticket (id={self.pk}, ticket_number={self.ticket_number}): {str(e)}")
            raise
    
    def get_status_color(self):
        """Retorna a cor do status"""
        colors = {
            'aberto': '#007bff',  # Azul
            'em_andamento': '#ffc107',  # Amarelo
            'aguardando_cliente': '#fd7e14',  # Laranja
            'resolvido': '#28a745',  # Verde
            'fechado': '#6c757d',  # Cinza
        }
        return colors.get(self.status, '#6c757d')
    
    def get_priority_color(self):
        """Retorna a cor da prioridade"""
        colors = {
            'baixa': '#6c757d',  # Cinza
            'normal': '#007bff',  # Azul
            'alta': '#ffc107',  # Amarelo
            'urgente': '#dc3545',  # Vermelho
        }
        return colors.get(self.priority, '#6c757d')
    
    def get_last_message(self):
        """Retorna a última mensagem do ticket"""
        return self.messages.order_by('-created_at').first()
    
    def get_unread_count(self, user):
        """Retorna quantidade de mensagens não lidas para o usuário"""
        if user == self.created_by:
            # Para o criador, contar mensagens enviadas por RM/atendentes
            return self.messages.filter(
                sent_by__role='RM',
                read=False
            ).count()
        elif user.is_rm_admin:
            # Para RM, contar mensagens enviadas pelo cliente
            return self.messages.filter(
                sent_by=self.created_by,
                read=False
            ).count()
        return 0
    
    def __str__(self):
        return f"{self.ticket_number} - {self.title}"


class TicketMessage(models.Model):
    """Modelo para mensagens do ticket (chat)"""
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name="Ticket"
    )
    message = models.TextField(verbose_name="Mensagem")
    sent_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='ticket_messages',
        verbose_name="Enviado por"
    )
    read = models.BooleanField(default=False, verbose_name="Lido")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Lido em")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    
    class Meta:
        verbose_name = "Mensagem do Ticket"
        verbose_name_plural = "Mensagens dos Tickets"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
            models.Index(fields=['sent_by', 'created_at']),
            models.Index(fields=['read']),
        ]
    
    def mark_as_read(self, user):
        """Marca a mensagem como lida"""
        if not self.read and self.sent_by != user:
            from django.utils import timezone
            self.read = True
            self.read_at = timezone.now()
            self.save()
    
    def __str__(self):
        return f"Mensagem {self.id} - Ticket {self.ticket.ticket_number}"


class TicketNotification(models.Model):
    """Modelo para notificações de tickets"""
    
    NOTIFICATION_TYPES = [
        ('ticket_created', 'Ticket Criado'),
        ('new_message', 'Nova Mensagem'),
        ('status_changed', 'Status Alterado'),
        ('assigned', 'Ticket Atribuído'),
        ('priority_changed', 'Prioridade Alterada'),
    ]
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Ticket"
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        verbose_name="Tipo de Notificação"
    )
    recipient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='ticket_notifications',
        verbose_name="Destinatário"
    )
    message = models.TextField(verbose_name="Mensagem")
    read = models.BooleanField(default=False, verbose_name="Lida", db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Lida em")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em", db_index=True)
    
    # Campos adicionais para contexto
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notifications',
        verbose_name="Criado por"
    )
    
    class Meta:
        verbose_name = "Notificação de Ticket"
        verbose_name_plural = "Notificações de Tickets"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'read', 'created_at']),
            models.Index(fields=['ticket', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
        ]
    
    def mark_as_read(self):
        """Marca a notificação como lida"""
        if not self.read:
            from django.utils import timezone
            self.read = True
            self.read_at = timezone.now()
            self.save()
    
    def __str__(self):
        return f"Notificação {self.id} - {self.get_notification_type_display()} - Ticket {self.ticket.ticket_number}"

# -----------------------------------------------------------------------------
# Controle opcional de sessão única por usuário
# -----------------------------------------------------------------------------
# Quando quiser garantir que apenas uma sessão permaneça ativa por usuário
# (último login derruba logins anteriores), descomente o bloco abaixo e execute
# `python manage.py makemigrations` seguido de `python manage.py migrate`.
#
# from django.contrib.auth import get_user_model
#
# class UserSession(models.Model):
#     user = models.OneToOneField(
#         get_user_model(),
#         on_delete=models.CASCADE,
#         related_name='active_session'
#     )
#     session_key = models.CharField(max_length=40, blank=True, null=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     def __str__(self):
#         return f"{self.user} - {self.session_key}"


class ConsentRecord(models.Model):
    """Registro de aceite de documentos legais (LGPD art. 8)."""

    DOCUMENT_TYPES = [
        ("terms", "Termos de Uso"),
        ("privacy", "Política de Privacidade"),
        ("cookies", "Política de Cookies"),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="consent_records",
        verbose_name="Usuário",
    )
    document_type = models.CharField(max_length=32, choices=DOCUMENT_TYPES)
    document_version = models.CharField(
        max_length=32,
        help_text="Versão do documento aceito (ex.: 2026-05-21)",
    )
    accepted_at = models.DateTimeField(auto_now_add=True, verbose_name="Aceito em")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    class Meta:
        verbose_name = "Registro de consentimento"
        verbose_name_plural = "Registros de consentimento"
        indexes = [
            models.Index(fields=["user", "document_type", "document_version"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "document_type", "document_version"],
                name="core_consent_unique_per_version",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.document_type} v{self.document_version}"


class DataSubjectRequest(models.Model):
    """Solicitações de titulares (portabilidade, exclusão, etc.)."""

    REQUEST_TYPES = [
        ("export", "Exportação de dados"),
        ("delete", "Eliminação de conta"),
        ("rectify", "Correção de dados"),
        ("other", "Outro"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pendente"),
        ("processing", "Em processamento"),
        ("completed", "Concluída"),
        ("rejected", "Rejeitada"),
        ("failed", "Falhou"),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="data_subject_requests",
    )
    request_type = models.CharField(max_length=16, choices=REQUEST_TYPES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Solicitação do titular"
        verbose_name_plural = "Solicitações dos titulares"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "request_type", "created_at"]),
        ]


class LgpdExportDownload(models.Model):
    """Artefato de exportação assinada com expiração (portabilidade ZIP)."""

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="lgpd_exports",
    )
    export_format = models.CharField(max_length=8, default="zip")
    storage_path = models.CharField(max_length=512, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    download_count = models.PositiveSmallIntegerField(default=0)
    max_downloads = models.PositiveSmallIntegerField(default=5)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Download de exportação LGPD"
        verbose_name_plural = "Downloads de exportação LGPD"
        ordering = ["-created_at"]

    @property
    def is_expired(self) -> bool:
        from django.utils import timezone

        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"Export #{self.pk} user={self.user_id} ({self.export_format})"


class TrustedDevice(models.Model):
    """Dispositivo confiável para MFA (remember device)."""

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="trusted_devices",
    )
    token_digest = models.CharField(max_length=64, db_index=True)
    device_label = models.CharField(max_length=128, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Dispositivo confiável MFA"
        verbose_name_plural = "Dispositivos confiáveis MFA"
        indexes = [
            models.Index(fields=["user", "token_digest"]),
        ]

    def __str__(self):
        return f"{self.user_id} — {self.device_label or 'device'}"


class UserSessionRecord(models.Model):
    """Sessões ativas por usuário (revogação e limite concorrente)."""

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="session_records",
    )
    session_key = models.CharField(max_length=64, db_index=True)
    access_token_digest = models.CharField(max_length=64, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Sessão de usuário"
        verbose_name_plural = "Sessões de usuários"
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
        ]

    def __str__(self):
        return f"session {self.session_key[:8]}… user={self.user_id}"


class AccountActivationToken(models.Model):
    """Token de uso único para ativação de conta e definição de senha (LGPD — sem senha por e-mail)."""

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="activation_tokens",
        verbose_name="Usuário",
    )
    token_digest = models.CharField(max_length=64, unique=True, db_index=True)
    django_token = models.CharField(
        max_length=128,
        blank=True,
        help_text="Token auxiliar (PasswordResetTokenGenerator) validado no servidor",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_ip = models.GenericIPAddressField(null=True, blank=True)
    used_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Token de ativação de conta"
        verbose_name_plural = "Tokens de ativação de conta"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "used_at", "expires_at"]),
        ]

    def __str__(self):
        status = "usado" if self.used_at else ("expirado" if self.is_expired else "ativo")
        return f"Ativação {self.user_id} — {status}"

    @property
    def is_expired(self):
        from django.utils import timezone

        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return self.used_at is None and not self.is_expired


class SecurityAuditEvent(models.Model):
    """Trilha de auditoria de segurança e LGPD (retenção configurável)."""

    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Aviso"),
        ("critical", "Crítico"),
    ]

    event_type = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="info", db_index=True)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_audit_events",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    correlation_id = models.CharField(max_length=64, blank=True, db_index=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Evento de auditoria"
        verbose_name_plural = "Eventos de auditoria"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["severity", "created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"