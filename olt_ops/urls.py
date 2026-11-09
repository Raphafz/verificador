from django.urls import path
from . import views

app_name = "olt_ops"

urlpatterns = [
    path("", views.olt_home, name="home"),
    path("vpn/", views.vpn_settings, name="vpn_settings"),
    path("vpn/testar/", views.vpn_test, name="vpn_test"),
    path("olts/", views.olt_list, name="olt_list"),
    path("olts/nova/", views.olt_create, name="olt_create"),
    path("olts/<int:pk>/editar/", views.olt_edit, name="olt_edit"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/ao-vivo/", views.job_live, name="job_live"),
    path("jobs/<int:pk>/status/", views.job_status, name="job_status"),
    path(
        "jobs/<int:pk>/listar-offline/",
        views.job_list_offline,
        name="job_list_offline",
    ),
    path(
        "jobs/<int:pk>/executar-exclusao/",
        views.job_execute_delete,
        name="job_execute_delete",
    ),
]
