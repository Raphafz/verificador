"""
Auditoria automática de segurança (OWASP / config).
python manage.py scan_security [--strict]
"""
import os
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Varredura de configuração e código — riscos de segurança"

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Exit code 1 se houver HIGH")

    def handle(self, *args, **options):
        findings: list[tuple[str, str, str]] = []  # severity, code, message

        if settings.DEBUG and getattr(settings, "IS_VPS", False):
            findings.append(("HIGH", "DEBUG_VPS", "DEBUG ativo em ambiente VPS"))

        from saas_viabilidade.security_bootstrap import validate_secret_key_strength

        if getattr(settings, "IS_PRODUCTION", False):
            for err in validate_secret_key_strength(settings.SECRET_KEY):
                findings.append(("HIGH", "SECRET_KEY", err))
        if getattr(settings, "SERVE_PUBLIC_MEDIA", False) and getattr(settings, "IS_PRODUCTION", False):
            findings.append(("HIGH", "MEDIA", "Mídia pública em produção"))

        if not os.getenv("FIELD_ENCRYPTION_KEY", "").strip() and not settings.DEBUG:
            findings.append(("MEDIUM", "FIELD_ENC", "FIELD_ENCRYPTION_KEY não configurada"))

        if getattr(settings, "MFA_REQUIRED", False) is False and not settings.DEBUG:
            findings.append(("LOW", "MFA", "MFA_REQUIRED desligado em produção"))

        if "*" in settings.ALLOWED_HOSTS:
            findings.append(("HIGH", "ALLOWED_HOSTS", "Wildcard em ALLOWED_HOSTS"))

        base = Path(settings.BASE_DIR)
        for py in (base / "saas_viabilidade").glob("*.py"):
            text = py.read_text(encoding="utf-8", errors="ignore")
            if re.search(r'print\s*\(\s*f?["\'].*(?:SECRET|PASSWORD|TOKEN)', text, re.I):
                findings.append(("MEDIUM", "PRINT_SECRET", f"Possível print sensível em {py.name}"))

        env_path = base / ".env"
        if env_path.exists() and (base / ".git").exists():
            findings.append(("LOW", "ENV_LOCAL", ".env presente — garantir .gitignore"))

        for sev, code, msg in findings:
            style = self.style.ERROR if sev == "HIGH" else self.style.WARNING
            self.stdout.write(style(f"[{sev}] {code}: {msg}"))

        if not findings:
            self.stdout.write(self.style.SUCCESS("Nenhum achado crítico."))
            return

        highs = [f for f in findings if f[0] == "HIGH"]
        if options["strict"] and highs:
            raise SystemExit(1)
