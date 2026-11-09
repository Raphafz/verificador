from django import forms

from .models import CompanyVpnConfig, OltEquipment, OnuCleanupJob





def _olt_queryset(company):

    return OltEquipment.objects.filter(company=company, is_active=True)





class OltEquipmentForm(forms.ModelForm):

    class Meta:

        model = OltEquipment

        fields = [

            "name",

            "host",

            "port",

            "vendor",

            "protocol",

            "username",

            "password",

            "enable_password",

            "list_command",

            "notes",

            "is_active",

        ]

        widgets = {

            "name": forms.TextInput(attrs={"class": "form-control"}),

            "host": forms.TextInput(attrs={"class": "form-control"}),

            "port": forms.NumberInput(attrs={"class": "form-control"}),

            "vendor": forms.Select(attrs={"class": "form-select"}),

            "protocol": forms.Select(attrs={"class": "form-select"}),

            "username": forms.TextInput(attrs={"class": "form-control"}),

            "password": forms.PasswordInput(

                render_value=False,

                attrs={"class": "form-control", "autocomplete": "new-password"},

            ),

            "enable_password": forms.PasswordInput(

                render_value=False,

                attrs={

                    "class": "form-control",

                    "autocomplete": "new-password",

                    "placeholder": "ZTE: senha do enable (ex. zxr10)",

                },

            ),

            "list_command": forms.TextInput(

                attrs={

                    "class": "form-control",

                    "placeholder": "Opcional — padrão por fabricante",

                },

            ),

            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),

            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),

        }

    def clean(self):
        cleaned = super().clean()
        protocol = cleaned.get("protocol") or "ssh"
        port = cleaned.get("port")
        if protocol == "telnet" and (not port or int(port) == 22):
            cleaned["port"] = 23
        elif protocol == "ssh" and not port:
            cleaned["port"] = 22
        return cleaned





class ListOfflineForm(forms.Form):

    olt = forms.ModelChoiceField(

        label="OLT",

        queryset=OltEquipment.objects.none(),

        widget=forms.Select(attrs={"class": "form-select"}),

    )

    gpon_port = forms.CharField(

        label="Porta GPON (F/S/P)",

        widget=forms.TextInput(

            attrs={"class": "form-control", "placeholder": "Ex: 0/1/14"},

        ),

    )



    def __init__(self, *args, company=None, **kwargs):

        super().__init__(*args, **kwargs)

        if company:

            self.fields["olt"].queryset = _olt_queryset(company)





class DeleteOnuForm(forms.Form):

    olt = forms.ModelChoiceField(

        label="OLT",

        queryset=OltEquipment.objects.none(),

        widget=forms.Select(attrs={"class": "form-select"}),

    )

    serial_numbers = forms.CharField(

        label="Serial numbers (SN)",

        widget=forms.Textarea(

            attrs={

                "class": "form-control font-monospace",

                "rows": 10,

                "placeholder": "Um SN por linha",

            },

        ),

    )

    def __init__(self, *args, company=None, **kwargs):

        super().__init__(*args, **kwargs)

        if company:

            self.fields["olt"].queryset = _olt_queryset(company)

    def clean_serial_numbers(self):

        text = self.cleaned_data.get("serial_numbers") or ""

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        if not lines:

            raise forms.ValidationError("Informe ao menos um serial.")

        return "\n".join(lines)





class CompanyVpnForm(forms.ModelForm):
    class Meta:
        model = CompanyVpnConfig
        fields = [
            "is_enabled",
            "name",
            "vpn_type",
            "ipsec_server",
            "ipsec_psk",
            "ovpn_content",
            "vpn_username",
            "vpn_password",
            "notes",
        ]
        widgets = {
            "is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "VPN Matriz"}),
            "vpn_type": forms.Select(attrs={"class": "form-select"}),
            "ipsec_server": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "138.204.76.0"},
            ),
            "ipsec_psk": forms.PasswordInput(
                render_value=True,
                attrs={"class": "form-control", "autocomplete": "off"},
            ),
            "ovpn_content": forms.Textarea(
                attrs={
                    "class": "form-control font-monospace",
                    "rows": 14,
                    "placeholder": "Cole aqui o conteúdo do arquivo .ovpn (OpenVPN)",
                },
            ),
            "vpn_username": forms.TextInput(attrs={"class": "form-control"}),
            "vpn_password": forms.PasswordInput(
                render_value=True,
                attrs={"class": "form-control", "autocomplete": "off"},
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("is_enabled"):
            return cleaned
        vpn_type = cleaned.get("vpn_type") or getattr(self.instance, "vpn_type", "openvpn")
        if vpn_type == "openvpn":
            if not (cleaned.get("ovpn_content") or "").strip():
                self.add_error("ovpn_content", "Cole o conteúdo do arquivo .ovpn.")
        elif vpn_type == "l2tp_ipsec":
            for field, label in (
                ("ipsec_server", "Informe o IP ou hostname do servidor VPN."),
                ("ipsec_psk", "Informe a chave pré-compartilhada (IPsec)."),
                ("vpn_username", "Informe o usuário VPN."),
                ("vpn_password", "Informe a senha VPN."),
            ):
                if not (cleaned.get(field) or "").strip():
                    self.add_error(field, label)
        return cleaned


class OnuCleanupJobForm(forms.ModelForm):

    """Legado — mantido para admin/histórico."""



    class Meta:

        model = OnuCleanupJob

        fields = ["olt", "gpon_port", "serial_numbers"]

        widgets = {

            "olt": forms.Select(attrs={"class": "form-select"}),

            "gpon_port": forms.TextInput(

                attrs={"class": "form-control", "placeholder": "0/1/14"},

            ),

            "serial_numbers": forms.Textarea(

                attrs={

                    "class": "form-control",

                    "rows": 12,

                    "placeholder": "Um serial por linha",

                },

            ),

        }



    def __init__(self, *args, company=None, **kwargs):

        super().__init__(*args, **kwargs)

        if company:

            self.fields["olt"].queryset = _olt_queryset(company)

