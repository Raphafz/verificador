"""
Inventário de dados pessoais (ROPA) — bases, finalidades e retenção por model.
"""
from __future__ import annotations

import json

from django.apps import apps
from django.core.management.base import BaseCommand

from core.lgpd_retention import get_retention_policies


# Campos sensíveis conhecidos por app.model
_PII_FIELDS = {
    "core.CustomUser": ["email", "phone", "first_name", "last_name", "cnpj"],
    "core.Company": ["cnpj", "email", "phone"],
    "core.ConsentRecord": ["ip_address", "user_agent"],
    "core.Ticket": ["title", "description"],
    "core.TicketMessage": ["message"],
    "core.DataSubjectRequest": ["details", "ip_address"],
    "core.SecurityAuditEvent": ["ip_address", "details"],
    "ftth_viewer.GeocodingCache": ["lat", "lng", "locality_hint"],
    "olt_ops.OltEquipment": ["password", "enable_password", "host"],
    "olt_ops.CompanyVpnConfig": ["vpn_password", "ipsec_psk"],
}


class Command(BaseCommand):
    help = "Inventário ROPA — dados pessoais por model e política de retenção"

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("json", "text"), default="text")
        parser.add_argument("--output", type=str, default="")

    def handle(self, *args, **options):
        inventory = {
            "ropa_version": "1.0",
            "processing_activities": self._activities(),
            "data_categories": self._data_categories(),
            "retention_policies": [
                {"name": p.name, "days": p.days, "model": p.model_label, "description": p.description}
                for p in get_retention_policies()
            ],
        }
        if options["format"] == "json":
            out = json.dumps(inventory, indent=2, ensure_ascii=False)
        else:
            out = self._to_text(inventory)
        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as f:
                f.write(out)
            self.stdout.write(self.style.SUCCESS(f"Salvo em {options['output']}"))
        else:
            self.stdout.write(out)

    def _activities(self) -> list[dict]:
        return [
            {
                "activity": "Autenticação e contas",
                "legal_basis": "Execução de contrato / legítimo interesse",
                "data_subjects": "Usuários empresa e RM",
                "systems": ["core.CustomUser", "core.ConsentRecord"],
            },
            {
                "activity": "Verificador FTTH / geocoding",
                "legal_basis": "Execução de contrato",
                "data_subjects": "Titulares indiretos (endereço minimizado)",
                "systems": ["ftth_viewer.GeocodingCache", "ftth_viewer.ViabilidadeCache"],
            },
            {
                "activity": "Suporte (tickets)",
                "legal_basis": "Execução de contrato",
                "data_subjects": "Usuários",
                "systems": ["core.Ticket", "core.TicketMessage"],
            },
            {
                "activity": "Operações OLT",
                "legal_basis": "Execução de contrato",
                "data_subjects": "Operadores técnicos",
                "systems": ["olt_ops.OltEquipment", "olt_ops.OnuCleanupJob"],
            },
            {
                "activity": "Alertas Telegram→WhatsApp",
                "legal_basis": "Execução de contrato",
                "data_subjects": "Clientes finais (indireto)",
                "systems": ["alerts.AlertBridgeConfig"],
            },
        ]

    def _data_categories(self) -> list[dict]:
        out = []
        for label, fields in _PII_FIELDS.items():
            try:
                app_label, model_name = label.split(".")
                model = apps.get_model(app_label, model_name)
                count = model.objects.count()
            except Exception:
                count = None
            out.append({
                "model": label,
                "pii_fields": fields,
                "approx_records": count,
            })
        return out

    def _to_text(self, inv: dict) -> str:
        lines = ["=== Inventário ROPA (dados pessoais) ===", ""]
        lines.append("Atividades de tratamento:")
        for a in inv["processing_activities"]:
            lines.append(f"  • {a['activity']} — {a['legal_basis']}")
            lines.append(f"    Sistemas: {', '.join(a['systems'])}")
        lines.append("\nCategorias / models:")
        for c in inv["data_categories"]:
            lines.append(f"  • {c['model']}: {', '.join(c['pii_fields'])} (~{c['approx_records']} reg.)")
        lines.append("\nRetenção:")
        for p in inv["retention_policies"]:
            lines.append(f"  • {p['name']}: {p['days']}d — {p['model']}")
        return "\n".join(lines)
