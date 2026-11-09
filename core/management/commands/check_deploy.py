"""
Validação pré-deploy — migrações, estáticos, segurança, env.
python manage.py check_deploy
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Checklist automatizado antes de deploy em produção"

    def handle(self, *args, **options):
        steps_ok = 0
        steps_total = 0

        def step(name, fn):
            nonlocal steps_ok, steps_total
            steps_total += 1
            try:
                fn()
                self.stdout.write(self.style.SUCCESS(f"  OK {name}"))
                steps_ok += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  FAIL {name}: {exc}"))

        self.stdout.write("=== check_deploy ===\n")

        step("Django check", lambda: call_command("check", verbosity=0))
        step("Migrações pendentes", self._check_migrations)
        step("Scan segurança", lambda: call_command("scan_security"))
        step("Validação ambiente", self._check_env)
        step("Health DB", self._check_db)

        self.stdout.write(f"\n{steps_ok}/{steps_total} passos OK")
        if steps_ok < steps_total:
            raise SystemExit(1)

    def _check_migrations(self):
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        if plan:
            raise RuntimeError(f"Existem {len(plan)} migração(ões) pendentes")

    def _check_env(self):
        from saas_viabilidade.env_validation import validate_environment
        from django.conf import settings
        issues = validate_environment(
            debug=settings.DEBUG,
            is_vps=getattr(settings, "IS_VPS", False),
            secret_key=settings.SECRET_KEY,
        )
        if issues:
            raise RuntimeError("; ".join(issues[:5]))

    def _check_db(self):
        with connection.cursor() as c:
            c.execute("SELECT 1")
