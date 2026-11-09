from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from . import password_reset as password_reset_views
from ftth_viewer import views as ftth_views

app_name = 'company'

urlpatterns = [
    # Autenticação da empresa
    path('login/', views.company_login_view, name='login'),
    # Troca LogoutView por view própria que aceita GET e redireciona para login da empresa
    path('logout/', views.company_logout_view, name='logout'),
    
    # Recuperação de senha (empresa)
    path('password-reset/', password_reset_views.CompanyPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', password_reset_views.CompanyPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', password_reset_views.CompanyPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', password_reset_views.CompanyPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Hub e painel da empresa
    path('hub/', views.company_hub, name='hub'),
    path('painel/', views.company_dashboard, name='dashboard'),

    # Módulo Alertas (ex-MENSAGENS)
    path('alertas/', include(('alerts.urls', 'alerts'), namespace='alerts')),

    # Módulo OLT/ONU (ex-Venda)
    path('olt/', include(('olt_ops.urls', 'olt_ops'), namespace='olt_ops')),
    
    # Verificador de viabilidade (todas as URLs do app, incluindo index e APIs)
    # O include já inclui a rota '' que é o index, então /verificador/ funciona
    path('verificador/', include(('ftth_viewer.urls', 'ftth_viewer'), namespace='ftth_viewer')),
    
    # Upload de mapas CTO (página de upload)
    path('upload/', views.company_map_upload_page, name='upload'),
    path('upload/arquivo/', views.company_map_upload, name='map_upload'),
    path('verificar-coordenadas/', views.company_verificar_coordenadas, name='verificar_coordenadas'),
    
    # Gestão de usuários da empresa (apenas admins)
    path('painel/usuarios/', views.company_user_list, name='user_list'),
    path('painel/usuarios/criar/', views.company_user_create, name='user_create'),
    path('painel/usuarios/<int:user_id>/editar/', views.company_user_edit, name='user_edit'),
    path('painel/usuarios/<int:user_id>/toggle/', views.company_user_toggle, name='user_toggle'),
    path('painel/usuarios/<int:user_id>/delete/', views.company_user_delete, name='user_delete'),
    
    # Gestão de mapas da empresa
    path('painel/mapas/', views.company_map_list, name='map_list'),
    path('painel/mapas/admin/', views.company_map_admin, name='map_admin'),
    path('painel/relatorios/', views.company_reports, name='reports'),
    path('mapas/<int:pk>/download/', views.company_map_download, name='map_download'),
    path('mapas/<int:pk>/delete/', views.company_map_delete, name='map_delete'),
    
    # Histórico de análises
    path('verificador/historico/', views.company_map_history, name='map_history'),
    
    # Sistema de tickets
    path('tickets/', views.company_ticket_list, name='ticket_list'),
    path('tickets/criar/', views.company_ticket_create, name='ticket_create'),
    path('tickets/<int:ticket_id>/', views.company_ticket_detail, name='ticket_detail'),
    path('tickets/<int:ticket_id>/mensagens/', views.get_new_messages, name='get_new_messages'),
    
    # Notificações de tickets
    path('notificacoes/', views.get_notifications, name='notifications'),
    path('notificacoes/contagem/', views.get_unread_count, name='notifications_count'),
    path('notificacoes/<int:notification_id>/ler/', views.mark_notification_read, name='mark_notification_read'),
    path('notificacoes/marcar-todas-lidas/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]