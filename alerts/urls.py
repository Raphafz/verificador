from django.urls import path

from . import views

app_name = "alerts"

urlpatterns = [
    path("config/", views.alert_settings, name="settings"),
    path("worker-status/", views.worker_status, name="worker_status"),
    path(
        "linhas/<int:line_id>/padrao/",
        views.whatsapp_line_set_default,
        name="line_set_default",
    ),
    path(
        "linhas/<int:line_id>/excluir/",
        views.whatsapp_line_delete,
        name="line_delete",
    ),
    path(
        "linhas/<int:line_id>/whatsapp/status/",
        views.whatsapp_status,
        name="whatsapp_status",
    ),
    path(
        "linhas/<int:line_id>/whatsapp/qr/",
        views.whatsapp_qr,
        name="whatsapp_qr",
    ),
    path(
        "linhas/<int:line_id>/whatsapp/conectar/",
        views.whatsapp_connect,
        name="whatsapp_connect",
    ),
    path(
        "linhas/<int:line_id>/whatsapp/desconectar/",
        views.whatsapp_disconnect,
        name="whatsapp_disconnect",
    ),
    path(
        "linhas/<int:line_id>/whatsapp/limpar-sessao/",
        views.whatsapp_clear_session,
        name="whatsapp_clear_session",
    ),
]
