from django.db import models

from core.encrypted_fields import EncryptedCharField


class AlertBridgeConfig(models.Model):
    """Configuração Telegram → destinos WhatsApp por empresa."""

    company = models.OneToOneField(
        "core.Company",
        on_delete=models.CASCADE,
        related_name="alert_bridge",
        verbose_name="Empresa",
    )
    is_active = models.BooleanField(default=False, verbose_name="Bridge ativo")
    telegram_bot_token = EncryptedCharField(
        max_length=512,
        blank=True,
        verbose_name="Token do bot Telegram",
        help_text="Obtenha em @BotFather",
    )
    telegram_group_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="ID do grupo Telegram",
        help_text="Deixe vazio para descobrir pelo log do worker na primeira mensagem",
    )
    whatsapp_alert_phones = models.TextField(
        blank=True,
        verbose_name="Telefones WhatsApp (PV)",
        help_text="Números que RECEBEM o alerta (DDI, vírgula). Ex: 5511999999999",
    )
    whatsapp_group_jid = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="JID do grupo WhatsApp",
        help_text="Alternativa aos telefones. Ex: 120363...@g.us",
    )
    message_prefix = models.CharField(max_length=32, default="[TG]", blank=True)
    filter_enabled = models.BooleanField(
        default=False,
        verbose_name="Usar filtro personalizado",
        help_text="Desmarcado = encaminha todas as mensagens de texto do grupo.",
    )
    filter_rules = models.TextField(
        blank=True,
        verbose_name="Regras de filtro",
        help_text="Uma condição por linha. A mensagem deve conter o texto (trecho exato).",
    )
    filter_match_all = models.BooleanField(
        default=False,
        verbose_name="Exigir todas as regras (E)",
        help_text="Desmarcado = basta uma regra (OU). Marcado = todas as linhas devem aparecer.",
    )
    antiban_enabled = models.BooleanField(default=True, verbose_name="Antiban ativo")
    antiban_delay_min_ms = models.PositiveIntegerField(default=1000)
    antiban_delay_max_ms = models.PositiveIntegerField(default=6000)
    antiban_warmup_sec = models.PositiveIntegerField(default=60)
    last_error = models.TextField(blank=True, verbose_name="Último erro do worker")
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Configuração de alertas"
        verbose_name_plural = "Configurações de alertas"

    def __str__(self):
        return f"Alertas — {self.company.name}"

    def whatsapp_phones_list(self):
        if not self.whatsapp_alert_phones.strip():
            return []
        return [
            "".join(c for c in p if c.isdigit())
            for p in self.whatsapp_alert_phones.split(",")
            if p.strip()
        ]

    def filter_rules_list(self):
        if not self.filter_rules.strip():
            return []
        return [line.strip() for line in self.filter_rules.splitlines() if line.strip()]

    def active_whatsapp_lines(self):
        return self.company.whatsapp_lines.filter(is_active=True).order_by(
            "-is_default", "sort_order", "label"
        )

    def default_whatsapp_line(self):
        return self.active_whatsapp_lines().filter(is_default=True).first()

    def sending_whatsapp_lines(self):
        """Linhas que participam do envio (multi-chip)."""
        qs = self.active_whatsapp_lines().filter(send_alerts=True)
        if qs.exists():
            return qs
        default_line = self.default_whatsapp_line()
        if default_line:
            return self.active_whatsapp_lines().filter(pk=default_line.pk)
        return self.active_whatsapp_lines()[:1]

    def to_worker_payload(self):
        lines = [
            line.to_worker_payload()
            for line in self.active_whatsapp_lines()
        ]
        sending = [line.to_worker_payload() for line in self.sending_whatsapp_lines()]
        default_line = self.default_whatsapp_line()
        return {
            "company_slug": self.company.slug,
            "company_name": self.company.name,
            "telegram_token": self.telegram_bot_token,
            "telegram_group_id": self.telegram_group_id or None,
            "whatsapp_alert_phones": self.whatsapp_phones_list(),
            "whatsapp_group_jid": self.whatsapp_group_jid or None,
            "message_prefix": self.message_prefix or "[TG]",
            "filter_enabled": self.filter_enabled,
            "filter_rules": self.filter_rules_list(),
            "filter_match_all": self.filter_match_all,
            "antiban_enabled": self.antiban_enabled,
            "antiban_delay_min_ms": self.antiban_delay_min_ms,
            "antiban_delay_max_ms": self.antiban_delay_max_ms,
            "antiban_warmup_sec": self.antiban_warmup_sec,
            "whatsapp_lines": lines,
            "sending_line_ids": [x["line_id"] for x in sending],
            "default_whatsapp_line_id": (
                str(default_line.pk) if default_line else (lines[0]["line_id"] if lines else None)
            ),
        }


class WhatsAppLine(models.Model):
    """Chip WhatsApp conectado (sessão Baileys) — vários por empresa."""

    WHATSAPP_LOGIN_QR = "qr"
    WHATSAPP_LOGIN_PAIRING = "pairing"
    WHATSAPP_LOGIN_CHOICES = [
        (WHATSAPP_LOGIN_QR, "QR Code"),
        (WHATSAPP_LOGIN_PAIRING, "Código de pareamento"),
    ]

    company = models.ForeignKey(
        "core.Company",
        on_delete=models.CASCADE,
        related_name="whatsapp_lines",
        verbose_name="Empresa",
    )
    label = models.CharField(
        max_length=80,
        verbose_name="Nome / identificação",
        help_text='Ex: "Chip Alertas 1", "Operação RJ"',
    )
    login_mode = models.CharField(
        max_length=16,
        choices=WHATSAPP_LOGIN_CHOICES,
        default=WHATSAPP_LOGIN_QR,
        verbose_name="Modo de conexão",
    )
    pairing_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Número (pareamento)",
        help_text="DDI+DDD+número, só dígitos. Obrigatório no modo pareamento.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Linha ativa")
    is_default = models.BooleanField(
        default=False,
        verbose_name="Chip principal",
        help_text="Referência visual no painel (legado). Use «Enviar alertas» nos chips.",
    )
    send_alerts = models.BooleanField(
        default=False,
        verbose_name="Enviar alertas",
        help_text="Pode marcar vários chips: o mesmo alerta sai por cada um conectado.",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Linha WhatsApp"
        verbose_name_plural = "Linhas WhatsApp"
        ordering = ["-is_default", "sort_order", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "label"],
                name="alerts_whatsappline_unique_label_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.label} ({self.company.slug})"

    def normalized_pairing_phone(self):
        raw = (self.pairing_phone or "").strip()
        return "".join(c for c in raw if c.isdigit())

    def session_key(self):
        """Pasta da sessão no worker: {company_slug}/{line_id}"""
        return f"{self.company.slug}/{self.pk}"

    def to_worker_payload(self):
        return {
            "line_id": str(self.pk),
            "label": self.label,
            "login_mode": self.login_mode or self.WHATSAPP_LOGIN_QR,
            "pairing_phone": self.normalized_pairing_phone(),
            "is_default": self.is_default,
            "send_alerts": self.send_alerts,
        }

    def save(self, *args, **kwargs):
        others = WhatsAppLine.objects.filter(company=self.company).exclude(pk=self.pk)
        if not others.exists():
            self.is_default = True
            if not self.send_alerts:
                self.send_alerts = True
        if self.is_default:
            others.filter(is_default=True).update(is_default=False)
        elif not others.filter(is_default=True).exists():
            self.is_default = True
        super().save(*args, **kwargs)


class AlertBridgeWorkerStatus(models.Model):
    """Heartbeat do worker Node que consome /api/internal/alert-bridge/configs/."""

    last_seen_at = models.DateTimeField(null=True, blank=True, verbose_name="Último poll")
    last_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP do worker")
    last_configs_count = models.PositiveIntegerField(default=0, verbose_name="Configs no último poll")
    worker_version = models.CharField(max_length=64, blank=True, verbose_name="Versão reportada")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Status do worker alert-bridge"
        verbose_name_plural = "Status do worker alert-bridge"

    def __str__(self):
        return f"Bridge worker — visto em {self.last_seen_at or 'nunca'}"

    @classmethod
    def touch(cls, *, ip: str | None = None, configs_count: int = 0, version: str = "") -> "AlertBridgeWorkerStatus":
        from django.utils import timezone

        obj, _ = cls.objects.get_or_create(pk=1)
        obj.last_seen_at = timezone.now()
        if ip:
            obj.last_ip = ip
        obj.last_configs_count = configs_count
        if version:
            obj.worker_version = version[:64]
        obj.save(
            update_fields=[
                "last_seen_at",
                "last_ip",
                "last_configs_count",
                "worker_version",
                "updated_at",
            ]
        )
        return obj

    @classmethod
    def get_status(cls) -> dict:
        from django.conf import settings
        from django.utils import timezone

        stale_minutes = int(getattr(settings, "BRIDGE_STALE_MINUTES", 5))
        obj = cls.objects.filter(pk=1).first()
        if not obj or not obj.last_seen_at:
            return {
                "healthy": False,
                "stale": True,
                "last_seen_at": None,
                "minutes_since": None,
                "message": "Worker alert-bridge nunca conectou.",
            }
        delta = timezone.now() - obj.last_seen_at
        minutes = int(delta.total_seconds() // 60)
        stale = minutes >= stale_minutes
        return {
            "healthy": not stale,
            "stale": stale,
            "last_seen_at": obj.last_seen_at,
            "last_ip": obj.last_ip,
            "last_configs_count": obj.last_configs_count,
            "worker_version": obj.worker_version,
            "minutes_since": minutes,
            "message": (
                f"Worker offline há {minutes} min (limite {stale_minutes} min)."
                if stale
                else f"Worker OK — último poll há {minutes} min."
            ),
        }

