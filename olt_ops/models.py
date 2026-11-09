from django.db import models

from core.encrypted_fields import EncryptedCharField


class OltEquipment(models.Model):
    """OLT cadastrada por empresa (substitui empresas.json do Venda)."""

    VENDOR_CHOICES = [
        ("huawei", "Huawei"),
        ("zte", "ZTE"),
    ]
    PROTOCOL_CHOICES = [
        ("ssh", "SSH"),
        ("telnet", "Telnet"),
    ]

    company = models.ForeignKey(
        "core.Company",
        on_delete=models.CASCADE,
        related_name="olt_equipment",
        verbose_name="Empresa",
    )
    name = models.CharField(max_length=120, verbose_name="Nome / identificação")
    host = models.CharField(max_length=255, verbose_name="IP ou hostname")
    host_vpn = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Host via VPN",
        help_text="Opcional. IP/hostname após conectar na VPN (vazio = usa o campo Host).",
    )
    port = models.PositiveIntegerField(default=22)
    vendor = models.CharField(max_length=16, choices=VENDOR_CHOICES, default="huawei")
    protocol = models.CharField(max_length=16, choices=PROTOCOL_CHOICES, default="ssh")
    username = models.CharField(max_length=128)
    password = EncryptedCharField(
        max_length=512,
        help_text="Armazenado criptografado no banco; restrinja acesso por perfil.",
    )
    enable_password = EncryptedCharField(
        max_length=512,
        blank=True,
        verbose_name="Senha enable (ZTE)",
        help_text=(
            "Opcional. Senha após o comando enable (ex.: zxr10). "
            "Vazio = usa a mesma senha de login."
        ),
    )
    notes = models.TextField(blank=True, verbose_name="Observações")
    list_command = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Comando listar offline",
        help_text=(
            "Vazio = padrão. Huawei: display ont info F S P all. "
            "ZTE: show run interface gpon-olt_F/S/P (+ power olt-rx). "
            "Opcional: só substitui o show run na ZTE."
        ),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "OLT"
        verbose_name_plural = "OLTs"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["company", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.host})"

    @property
    def connection_port(self) -> int:
        if self.port:
            return int(self.port)
        return 23 if self.protocol == "telnet" else 22

    def zte_enable_secret(self) -> str:
        """Senha do enable na ZTE (login e enable costumam ser diferentes)."""
        secret = (self.enable_password or "").strip()
        return secret or (self.password or "").strip()


class CompanyVpnConfig(models.Model):
    """VPN da empresa — o servidor SaaS conecta antes de acessar OLTs na rede interna."""

    VPN_TYPE_CHOICES = [
        ("openvpn", "OpenVPN (.ovpn)"),
        ("l2tp_ipsec", "L2TP/IPsec (chave pré-compartilhada)"),
    ]

    company = models.OneToOneField(
        "core.Company",
        on_delete=models.CASCADE,
        related_name="vpn_config",
        verbose_name="Empresa",
    )
    is_enabled = models.BooleanField(
        default=False,
        verbose_name="Usar VPN nas operações OLT",
    )
    name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Nome / identificação",
        help_text="Ex: VPN Matriz SP",
    )
    vpn_type = models.CharField(
        max_length=32,
        choices=VPN_TYPE_CHOICES,
        default="openvpn",
    )
    ovpn_content = models.TextField(
        blank=True,
        verbose_name="Arquivo .ovpn",
        help_text="Cole o conteúdo completo do arquivo .ovpn (somente para OpenVPN).",
    )
    ipsec_server = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Servidor VPN (IP ou hostname)",
        help_text="Ex.: 138.204.76.0 — usado em L2TP/IPsec.",
    )
    ipsec_psk = EncryptedCharField(
        max_length=512,
        blank=True,
        verbose_name="Chave pré-compartilhada (IPsec)",
        help_text="PSK configurada no gateway / no Windows como “chave”.",
    )
    vpn_username = models.CharField(max_length=128, blank=True, verbose_name="Usuário VPN")
    vpn_password = EncryptedCharField(
        max_length=512,
        blank=True,
        verbose_name="Senha VPN",
        help_text="Usado se o .ovpn tiver auth-user-pass.",
    )
    notes = models.TextField(blank=True, verbose_name="Observações")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "VPN da empresa"
        verbose_name_plural = "VPNs das empresas"

    def __str__(self):
        label = self.name or "VPN"
        return f"{label} — {self.company.name}"

    def is_configured(self) -> bool:
        if not self.is_enabled:
            return False
        if self.vpn_type == "openvpn":
            return bool(self.ovpn_content.strip())
        if self.vpn_type == "l2tp_ipsec":
            return bool(
                self.ipsec_server.strip()
                and self.ipsec_psk.strip()
                and self.vpn_username.strip()
                and self.vpn_password.strip()
            )
        return False

    @property
    def type_label(self) -> str:
        return self.get_vpn_type_display()

    @property
    def summary_label(self) -> str:
        if self.name:
            return self.name
        return self.type_label


class OnuCleanupJob(models.Model):
    """Job de listagem/remoção de ONUs (fluxo do Venda)."""

    STATUS_CHOICES = [
        ("draft", "Rascunho"),
        ("queued", "Na fila"),
        ("listing", "Listando offline"),
        ("ready", "Pronto para excluir"),
        ("running", "Excluindo"),
        ("done", "Concluído"),
        ("failed", "Falhou"),
    ]

    company = models.ForeignKey(
        "core.Company",
        on_delete=models.CASCADE,
        related_name="onu_jobs",
    )
    olt = models.ForeignKey(
        OltEquipment,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    gpon_port = models.CharField(
        max_length=32,
        verbose_name="Porta GPON (F/S/P)",
        help_text="Ex: 0/1/14",
    )
    serial_numbers = models.TextField(
        blank=True,
        help_text="Um SN por linha",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    pending_operation = models.CharField(
        max_length=8,
        blank=True,
        choices=[("list", "Listagem"), ("delete", "Exclusão")],
        verbose_name="Operação pendente (fila)",
    )
    log_output = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "core.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="onu_jobs_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Job ONU"
        verbose_name_plural = "Jobs ONU"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Job {self.id} — {self.olt.name} {self.gpon_port}"

    def serial_list(self):
        return [ln.strip() for ln in self.serial_numbers.splitlines() if ln.strip()]


class CompanyOltExecutionConfig(models.Model):
    """Como executar jobs OLT/VPN desta empresa (host legado vs container isolado)."""

    WORKER_MODE_CHOICES = [
        ("", "Padrão global (.env)"),
        ("host", "Processo no host (thread + mutex VPN)"),
        ("container", "Container Docker (rede isolada por job)"),
    ]

    company = models.OneToOneField(
        "core.Company",
        on_delete=models.CASCADE,
        related_name="olt_execution",
        verbose_name="Empresa",
    )
    worker_mode = models.CharField(
        max_length=16,
        choices=WORKER_MODE_CHOICES,
        blank=True,
        default="",
        verbose_name="Modo de execução",
        help_text="Vazio = usa OLT_EXECUTION_MODE do .env",
    )
    max_concurrent_jobs = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Jobs paralelos máx.",
        help_text="0 = usa OLT_MAX_PARALLEL_JOBS do .env",
    )
    notes = models.TextField(blank=True, verbose_name="Observações")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Execução OLT da empresa"
        verbose_name_plural = "Execuções OLT das empresas"

    def __str__(self):
        mode = self.worker_mode or "global"
        return f"Execução OLT — {self.company.name} ({mode})"

    def resolved_worker_mode(self) -> str:
        from django.conf import settings

        if self.worker_mode:
            return self.worker_mode
        return getattr(settings, "OLT_EXECUTION_MODE", "host")

    def resolved_max_concurrent_jobs(self) -> int:
        from django.conf import settings

        if self.max_concurrent_jobs:
            return int(self.max_concurrent_jobs)
        return int(getattr(settings, "OLT_MAX_PARALLEL_JOBS", 5))
