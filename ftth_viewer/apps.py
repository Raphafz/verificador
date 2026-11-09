from django.apps import AppConfig


class FtthViewerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ftth_viewer'
    verbose_name = 'FTTH Viewer'
    
    def ready(self):
        # Importar signals se necessário
        pass

