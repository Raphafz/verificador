from django import forms

from .models import AlertBridgeConfig, WhatsAppLine


class AlertBridgeConfigForm(forms.ModelForm):
    class Meta:
        model = AlertBridgeConfig
        fields = [
            "is_active",
            "telegram_bot_token",
            "telegram_group_id",
            "whatsapp_alert_phones",
            "whatsapp_group_jid",
            "message_prefix",
            "filter_enabled",
            "filter_rules",
            "filter_match_all",
            "antiban_enabled",
            "antiban_delay_min_ms",
            "antiban_delay_max_ms",
            "antiban_warmup_sec",
        ]
        widgets = {
            "telegram_bot_token": forms.PasswordInput(
                render_value=True,
                attrs={"class": "form-control", "autocomplete": "off"},
            ),
            "telegram_group_id": forms.TextInput(attrs={"class": "form-control"}),
            "whatsapp_alert_phones": forms.Textarea(
                attrs={"class": "form-control", "rows": 2},
            ),
            "whatsapp_group_jid": forms.TextInput(attrs={"class": "form-control"}),
            "message_prefix": forms.TextInput(attrs={"class": "form-control"}),
            "filter_rules": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Ex:\nAlto uso de largura de banda\n(LINK.K2)\nLINK.INOVA",
                },
            ),
            "antiban_delay_min_ms": forms.NumberInput(attrs={"class": "form-control"}),
            "antiban_delay_max_ms": forms.NumberInput(attrs={"class": "form-control"}),
            "antiban_warmup_sec": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "filter_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "filter_match_all": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "antiban_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_active"):
            if not cleaned.get("telegram_bot_token"):
                self.add_error("telegram_bot_token", "Obrigatório com bridge ativo.")
            phones = cleaned.get("whatsapp_alert_phones", "")
            jid = cleaned.get("whatsapp_group_jid", "")
            if not phones.strip() and not jid.strip():
                self.add_error(
                    "whatsapp_alert_phones",
                    "Informe telefones ou JID do grupo WhatsApp.",
                )
        if cleaned.get("filter_enabled") and not (cleaned.get("filter_rules") or "").strip():
            self.add_error(
                "filter_rules",
                "Informe ao menos uma linha de filtro ou desative o filtro personalizado.",
            )
        return cleaned


class WhatsAppLineForm(forms.ModelForm):
    class Meta:
        model = WhatsAppLine
        fields = [
            "label",
            "login_mode",
            "pairing_phone",
            "is_active",
            "is_default",
            "send_alerts",
        ]
        widgets = {
            "label": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Chip Alertas 1"},
            ),
            "login_mode": forms.RadioSelect(),
            "pairing_phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "5521999999999",
                    "inputmode": "numeric",
                },
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "send_alerts": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("login_mode") or WhatsAppLine.WHATSAPP_LOGIN_QR
        phone = (cleaned.get("pairing_phone") or "").strip()
        digits = "".join(c for c in phone if c.isdigit())
        if mode == WhatsAppLine.WHATSAPP_LOGIN_PAIRING and len(digits) < 10:
            self.add_error(
                "pairing_phone",
                "Informe o número com DDI para o modo pareamento.",
            )
        else:
            cleaned["pairing_phone"] = digits
        return cleaned
