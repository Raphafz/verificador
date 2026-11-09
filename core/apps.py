from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.ticket_signals  # noqa: F401
        import core.signals_session_security  # noqa: F401
