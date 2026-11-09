"""
runserver: Django + worker MENSAGENS (deve carregar após django.contrib.staticfiles).
"""
from django.contrib.staticfiles.management.commands.runserver import (
    Command as StaticfilesRunserverCommand,
)

from core.alert_bridge_runner import AlertBridgeRunner, should_run_alert_bridge


class Command(StaticfilesRunserverCommand):
    help = (
        "Servidor de desenvolvimento Django + worker MENSAGENS (alertas). "
        "Use --no-bridge para só o Django."
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--no-bridge",
            action="store_true",
            help="Não iniciar o worker MENSAGENS.",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bridge_runner: AlertBridgeRunner | None = None

    def handle(self, *args, **options):
        try:
            return super().handle(*args, **options)
        finally:
            if self._bridge_runner:
                self._bridge_runner.stop()

    def inner_run(self, *args, **options):
        if not options.get("no_bridge") and should_run_alert_bridge():
            host, port = self._parse_addrport(options.get("addrport"))
            self._bridge_runner = AlertBridgeRunner(host=host, port=port)
            import threading

            threading.Thread(
                target=self._bridge_runner.start_when_server_ready,
                name="alert-bridge-starter",
                daemon=True,
            ).start()
        elif options.get("no_bridge"):
            print("[alert-bridge] Worker desativado (--no-bridge).")
        elif not should_run_alert_bridge():
            print(
                "[alert-bridge] Worker só sobe com DEBUG=true "
                "(RUN_ALERT_BRIDGE no .env)."
            )

        return super().inner_run(*args, **options)

    def _parse_addrport(self, addrport) -> tuple[str, int]:
        if not addrport:
            return "127.0.0.1", 8000
        if isinstance(addrport, (list, tuple)):
            addrport = addrport[0] if addrport else "127.0.0.1:8000"
        text = str(addrport)
        if ":" in text:
            host, port_str = text.rsplit(":", 1)
            try:
                return host or "127.0.0.1", int(port_str)
            except ValueError:
                return "127.0.0.1", 8000
        return text, 8000
