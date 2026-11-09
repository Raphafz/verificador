"""
Verificação enterprise de segurança para deploy.
  python manage.py check_security
  python manage.py check_security --deploy
  python manage.py check_security --generate-secret-key
"""
from __future__ import annotations

import os
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from saas_viabilidade.env_validation import validate_environment
from saas_viabilidade.security_bootstrap import (
    generate_secret_key,
    validate_field_encryption_key_strength,
    validate_secret_key_strength,
)


class Command(BaseCommand):
    help = "Auditoria de segurança para deploy (DEBUG, secrets, cookies, HTTPS, CSP, MFA, mídia)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--deploy",
            action="store_true",
            help="Modo estrito de deploy (equivalente a check --deploy + regras enterprise)",
        )
        parser.add_argument(
            "--generate-secret-key",
            action="store_true",
            help="Imprime SECRET_KEY segura para colar no .env",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit code 1 se houver falhas",
        )

    def handle(self, *args, **options):
        if options["generate_secret_key"]:
            key = generate_secret_key()
            self.stdout.write(self.style.SUCCESS("SECRET_KEY gerada (copie para o .env):"))
            self.stdout.write(f"SECRET_KEY={key}")
            return

        failures: list[str] = []
        warnings: list[str] = []

        is_prod = getattr(settings, "IS_PRODUCTION", False)
        debug = settings.DEBUG

        self.stdout.write(f"Ambiente: IS_PRODUCTION={is_prod} DEBUG={debug} IS_VPS={getattr(settings, 'IS_VPS', False)}")

        if debug and is_prod:
            failures.append("DEBUG=True em ambiente de produção")
        if debug and getattr(settings, "IS_VPS", False):
            failures.append("DEBUG=True na VPS")

        sk_issues = validate_secret_key_strength(settings.SECRET_KEY)
        if is_prod and sk_issues:
            failures.extend([f"SECRET_KEY: {x}" for x in sk_issues])
        elif sk_issues:
            warnings.extend([f"SECRET_KEY (dev): {x}" for x in sk_issues])

        env_issues = validate_environment(
            debug=debug,
            is_vps=getattr(settings, "IS_VPS", False),
            secret_key=settings.SECRET_KEY,
        )
        for msg in env_issues:
            if is_prod:
                failures.append(msg)
            else:
                warnings.append(msg)

        if not getattr(settings, "SESSION_COOKIE_SECURE", False) and is_prod:
            failures.append("SESSION_COOKIE_SECURE deve ser True em produção")
        if not getattr(settings, "CSRF_COOKIE_SECURE", False) and is_prod:
            failures.append("CSRF_COOKIE_SECURE deve ser True em produção")
        if not getattr(settings, "CSRF_COOKIE_HTTPONLY", False) and is_prod:
            failures.append("CSRF_COOKIE_HTTPONLY deve ser True em produção")

        if is_prod and not getattr(settings, "SECURE_SSL_REDIRECT", False):
            failures.append("SECURE_SSL_REDIRECT deve ser True em produção")
        if is_prod and not getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
            failures.append("SECURE_PROXY_SSL_HEADER não configurado (necessário atrás de Nginx)")

        if getattr(settings, "SERVE_PUBLIC_MEDIA", False) and is_prod:
            failures.append("SERVE_PUBLIC_MEDIA ativo em produção")
        if is_prod and getattr(settings, "SERVE_MEDIA_VIA_DJANGO", False):
            failures.append("SERVE_MEDIA_VIA_DJANGO=true em produção")

        if not getattr(settings, "USE_PROTECTED_MEDIA", True) and is_prod:
            warnings.append("USE_PROTECTED_MEDIA=False — confirme que Nginx protege /media/")

        if not getattr(settings, "CSP_STRICT", False) and is_prod:
            warnings.append("CSP_STRICT=False em produção")

        if not getattr(settings, "MFA_REQUIRED", False) and is_prod:
            warnings.append("MFA_REQUIRED=False em produção")

        fek = os.getenv("FIELD_ENCRYPTION_KEY", "").strip()
        fek_issues = validate_field_encryption_key_strength(fek)
        if is_prod and fek_issues:
            failures.extend([f"FIELD_ENCRYPTION_KEY: {x}" for x in fek_issues])
        elif fek_issues:
            warnings.extend([f"FIELD_ENCRYPTION_KEY (dev): {x}" for x in fek_issues])

        hmac_s = os.getenv("BRIDGE_HMAC_SECRET", "").strip()
        token_b = os.getenv("ALERT_BRIDGE_API_TOKEN", "").strip()
        if is_prod and not hmac_s:
            failures.append("BRIDGE_HMAC_SECRET ausente em produção")
        if is_prod and hmac_s and token_b and hmac_s == token_b:
            failures.append("BRIDGE_HMAC_SECRET deve ser diferente de ALERT_BRIDGE_API_TOKEN")
        if is_prod and not os.getenv("REDIS_URL", "").strip():
            warnings.append("REDIS_URL ausente — anti-replay bridge pode falhar entre workers")

        if options["deploy"]:
            from django.core.management import call_command
            from io import StringIO
            err = StringIO()
            try:
                call_command("check", deploy=True, stdout=err, stderr=err)
            except SystemExit as exc:
                if exc.code:
                    failures.append(f"django check --deploy falhou (code {exc.code})")

        for w in warnings:
            self.stdout.write(self.style.WARNING(f"WARN: {w}"))
        for f in failures:
            self.stdout.write(self.style.ERROR(f"FAIL: {f}"))

        if failures:
            self.stdout.write(self.style.ERROR(f"\n{len(failures)} falha(s) de segurança."))
            if options["strict"] or options["deploy"]:
                raise CommandError("Verificação de segurança falhou")
            return

        self.stdout.write(self.style.SUCCESS("\nVerificação de segurança OK."))
