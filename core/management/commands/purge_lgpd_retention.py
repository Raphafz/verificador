"""
Purge global LGPD — caches, tokens, auditoria, consentimentos, tickets, exports, OLT.
Cron: 0 4 * * * python manage.py purge_lgpd_retention
"""
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.lgpd_anonymization import purge_closed_tickets_older_than, purge_consent_records_older_than
from core.lgpd_export import purge_expired_exports
from core.lgpd_retention import cutoff_for_days, get_retention_policies, policy_days
from core.models import AccountActivationToken, DataSubjectRequest, SecurityAuditEvent


class Command(BaseCommand):
    help = "Aplica políticas de retenção LGPD configuráveis (global)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        self.stdout.write("Políticas de retenção:")
        for p in get_retention_policies():
            self.stdout.write(f"  - {p.name}: {p.days}d — {p.model_label or p.description}")

        if dry:
            self.stdout.write(self.style.WARNING("Dry-run — nenhuma exclusão"))
            return

        call_command("purge_old_caches")
        call_command("purge_activation_tokens")
        call_command("purge_geocoding_cache")
        call_command("purge_olt_logs", days=policy_days("olt_job_logs", 7))

        audit_days = int(settings.AUDIT_RETENTION_DAYS)
        n_audit, _ = SecurityAuditEvent.objects.filter(
            created_at__lt=cutoff_for_days(audit_days)
        ).delete()
        self.stdout.write(f"Auditoria: {n_audit} eventos > {audit_days}d removidos")

        act_days = int(settings.ACTIVATION_TOKEN_RETENTION_DAYS)
        acut = cutoff_for_days(act_days)
        n_act, _ = AccountActivationToken.objects.filter(created_at__lt=acut).exclude(
            used_at__isnull=True,
            expires_at__gte=timezone.now(),
        ).delete()
        self.stdout.write(f"Tokens ativação: {n_act} removidos (> {act_days}d)")

        consent_days = int(settings.CONSENT_RETENTION_DAYS)
        n_consent = purge_consent_records_older_than(cutoff_for_days(consent_days))
        self.stdout.write(f"Consentimentos: {n_consent} removidos (> {consent_days}d)")

        dsr_days = int(settings.DSR_RETENTION_DAYS)
        n_dsr, _ = DataSubjectRequest.objects.filter(
            status__in=("completed", "rejected", "failed"),
            completed_at__lt=cutoff_for_days(dsr_days),
        ).delete()
        self.stdout.write(f"DSR arquivados: {n_dsr} removidos")

        ticket_days = int(getattr(settings, "TICKET_RETENTION_DAYS", 730))
        n_tickets = purge_closed_tickets_older_than(cutoff_for_days(ticket_days))
        self.stdout.write(f"Tickets fechados: {n_tickets} anonimizados (> {ticket_days}d)")

        n_exports = purge_expired_exports()
        self.stdout.write(f"Exports LGPD expirados: {n_exports} removidos")

        pending_max = int(getattr(settings, "DSR_PENDING_MAX_DAYS", 30))
        stale = DataSubjectRequest.objects.filter(
            status="pending",
            request_type="delete",
            created_at__lt=cutoff_for_days(pending_max),
        ).count()
        if stale:
            self.stdout.write(
                self.style.WARNING(
                    f"DSR exclusão pendente há >{pending_max}d: {stale} — revisar manualmente"
                )
            )

        self.stdout.write(self.style.SUCCESS("Retenção LGPD concluída"))
