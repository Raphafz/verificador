"""
Processa solicitações pendentes de eliminação (LGPD) — cron-ready, retries, auditoria.

Uso: python manage.py process_data_subject_requests [--dry-run] [--notify]

Cron: 0 3 * * * python manage.py process_data_subject_requests --notify
"""
import logging
import time

from django.conf import settings
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.audit_trail import record_security_event
from core.lgpd_anonymization import (
    anonymize_user_account,
    complete_dsr,
    fail_dsr,
    mark_dsr_processing,
)
from core.models import DataSubjectRequest

logger = logging.getLogger("audit")


class Command(BaseCommand):
    help = "Anonimiza contas com solicitação de exclusão pendente e já desativadas"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--request-id", type=int)
        parser.add_argument("--max-retries", type=int, default=None)
        parser.add_argument("--notify", action="store_true")
        parser.add_argument("--sleep", type=float, default=0.0)

    def handle(self, *args, **options):
        max_retries = options["max_retries"] or int(
            getattr(settings, "DSR_MAX_RETRIES", 3)
        )
        qs = DataSubjectRequest.objects.filter(
            request_type="delete",
            status__in=("pending", "failed"),
        ).select_related("user")
        if options["request_id"]:
            qs = qs.filter(pk=options["request_id"])

        if not qs.exists():
            self.stdout.write("Nenhuma solicitação de exclusão pendente.")
            return

        processed = failed = 0
        for req in qs:
            if self._process_one(req, options, max_retries):
                processed += 1
            else:
                failed += 1
            if options["sleep"]:
                time.sleep(float(options["sleep"]))

        summary = f"LGPD exclusão: {processed} concluída(s), {failed} falha(s)/ignorada(s)."
        self.stdout.write(self.style.SUCCESS(summary) if failed == 0 else summary)

        if options["notify"] and (processed or failed):
            self._notify_admins(summary)

    def _process_one(self, req: DataSubjectRequest, options, max_retries: int) -> bool:
        user = req.user

        if user.is_active:
            self.stdout.write(
                self.style.WARNING(f"#{req.pk} usuário {user.username} ainda ativo — ignorado")
            )
            return False

        if user.is_superuser or getattr(user, "is_rm_admin", False):
            self.stdout.write(self.style.ERROR(f"#{req.pk} conta RM/superuser — rejeitar manualmente"))
            if not options["dry_run"]:
                req.status = "rejected"
                req.details = (req.details or "") + "\nRejeitado: conta administrativa."
                req.completed_at = timezone.now()
                req.save(update_fields=["status", "details", "completed_at"])
                record_security_event(
                    "lgpd_delete_rejected",
                    details={"request_id": req.pk, "reason": "admin_account"},
                )
            return False

        if req.retry_count >= max_retries and req.status == "failed":
            self.stdout.write(self.style.WARNING(f"#{req.pk} já em falha definitiva"))
            return False

        self.stdout.write(
            f"{'[dry-run] ' if options['dry_run'] else ''}Anonimizar #{req.pk} -> {user.username}"
        )
        if options["dry_run"]:
            return True

        mark_dsr_processing(req)
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                subject_hash = anonymize_user_account(user)
                complete_dsr(
                    req,
                    detail_suffix=(
                        f"\nConta anonimizada em {timezone.now().isoformat()} "
                        f"(tentativa {attempt}/{max_retries}, hash={subject_hash[:12]}…)."
                    ),
                )
                record_security_event(
                    "lgpd_delete_completed",
                    details={"request_id": req.pk, "subject_hash": subject_hash[:16]},
                )
                self.stdout.write(self.style.SUCCESS(f"  Concluído #{req.pk}"))
                return True
            except Exception as exc:
                last_error = exc
                logger.exception("Falha ao anonimizar #%s tentativa %s", req.pk, attempt)
                if attempt < max_retries:
                    time.sleep(min(2 ** attempt, 30))

        final = req.retry_count + 1 >= max_retries
        fail_dsr(req, str(last_error), final=final)
        if final:
            mail_admins(
                subject=f"[LGPD] Falha definitiva exclusão #{req.pk}",
                message=str(last_error),
                fail_silently=True,
            )
        return False

    def _notify_admins(self, summary: str):
        try:
            mail_admins(
                subject="[LGPD] Processamento de exclusões",
                message=summary,
                fail_silently=True,
            )
        except Exception:
            logger.warning("Não foi possível notificar admins: %s", summary)
