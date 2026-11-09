"""Checklist de onboarding de nova empresa ISP."""
from django.core.management.base import BaseCommand, CommandError

from core.models import Company, CustomUser, CTOMapFile


class Command(BaseCommand):
    help = "Exibe checklist de onboarding para uma empresa (slug ou id)."

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, help="Slug da empresa")
        parser.add_argument("--id", type=int, help="ID da empresa")

    def handle(self, *args, **options):
        company = self._resolve_company(options)
        users = CustomUser.objects.filter(company=company, is_active=True)
        admins = users.filter(role="COMPANY_ADMIN")
        maps = CTOMapFile.objects.filter(company=company).count()

        checks = [
            ("Empresa ativa", company.is_active),
            (f"Plano definido ({company.plan_code})", bool(company.plan_code)),
            ("Módulo verificador", company.module_verificador),
            ("Módulo alertas", company.module_alertas),
            ("Módulo OLT", company.module_olt),
            ("Admin da empresa criado", admins.exists()),
            ("Pelo menos 1 usuário ativo", users.exists()),
            ("Mapa CTO enviado", maps > 0 or not company.module_verificador),
        ]

        if company.module_alertas:
            has_bridge = hasattr(company, "alert_bridge")
            checks.append(("Config alertas criada", has_bridge))
            if has_bridge:
                cfg = company.alert_bridge
                checks.append(("Token Telegram", bool(cfg.telegram_bot_token)))
                checks.append(("Linha WhatsApp", company.whatsapp_lines.filter(is_active=True).exists()))

        if company.module_olt:
            from olt_ops.models import OltEquipment

            checks.append(("OLT cadastrada", OltEquipment.objects.filter(company=company, is_active=True).exists()))

        self.stdout.write(self.style.MIGRATE_HEADING(f"Onboarding — {company.name} ({company.slug})"))
        done = 0
        for label, ok in checks:
            mark = self.style.SUCCESS("OK") if ok else self.style.WARNING("PENDENTE")
            self.stdout.write(f"  [{mark}] {label}")
            if ok:
                done += 1
        self.stdout.write("")
        self.stdout.write(f"Progresso: {done}/{len(checks)}")
        if done < len(checks):
            self.stdout.write("Próximo passo: complete itens PENDENTE (ver docs/PLATAFORMA-UNIFICADA.md).")

    def _resolve_company(self, options):
        if options.get("slug"):
            try:
                return Company.objects.get(slug=options["slug"])
            except Company.DoesNotExist as exc:
                raise CommandError(f"Empresa não encontrada: {options['slug']}") from exc
        if options.get("id"):
            try:
                return Company.objects.get(pk=options["id"])
            except Company.DoesNotExist as exc:
                raise CommandError(f"Empresa id={options['id']} não encontrada") from exc
        raise CommandError("Informe --slug ou --id")
