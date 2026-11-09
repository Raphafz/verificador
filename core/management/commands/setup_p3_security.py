"""
Checklist P3 (RELATORIO-P3.md): DPO, backup GPG, media, comandos sensíveis.
"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verifica checklist de segurança P3"

    def handle(self, *args, **options):
        dpo = getattr(settings, "DPO_EMAIL", "") or "não configurado"
        self.stdout.write(self.style.SUCCESS(f"DPO_EMAIL: {dpo}"))

        serve_media = getattr(settings, "SERVE_MEDIA_VIA_DJANGO", False)
        if settings.DEBUG:
            self.stdout.write("Mídia: Django serve /media/ (DEBUG)")
        elif serve_media:
            self.stdout.write(self.style.WARNING("Mídia: Django serve /media/ em produção — prefira Nginx"))
        else:
            self.stdout.write(self.style.SUCCESS("Mídia: não exposta via Django em produção"))

        import os

        if os.getenv("BACKUP_GPG_PASSPHRASE_FILE"):
            self.stdout.write(self.style.SUCCESS("Backup GPG: passphrase file configurado"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Backup GPG: defina BACKUP_GPG_PASSPHRASE_FILE no .env para criptografar backups"
                )
            )

        self.stdout.write("")
        self.stdout.write("Scripts:")
        self.stdout.write("  scripts/cron-purge-caches.sh")
        self.stdout.write("  backup-db.sh (suporte GPG)")
        self.stdout.write("")
        self.stdout.write("Comandos:")
        self.stdout.write("  python manage.py purge_old_caches")
        self.stdout.write("  python manage.py process_data_subject_requests --dry-run")
