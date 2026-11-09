from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import password_reset as password_reset_views
from . import mfa_views
from . import session_views

app_name = 'rm'

urlpatterns = [
    # Autenticação RM
    path('login/', views.rm_login_view, name='login'),
    path('mfa/verify/', mfa_views.mfa_verify, name='mfa_verify'),
    path('mfa/setup/', mfa_views.mfa_setup, name='mfa_setup'),
    path('mfa/recovery/', mfa_views.mfa_recovery, name='mfa_recovery'),
    path('mfa/devices/', mfa_views.mfa_trusted_devices, name='mfa_trusted_devices'),
    path('sessoes/', session_views.my_sessions, name='my_sessions'),
    path('sessoes/<int:session_id>/revogar/', session_views.revoke_session, name='revoke_session'),
    path('sessoes/revogar-outras/', session_views.revoke_all_other_sessions, name='revoke_all_sessions'),
    # Troca LogoutView por view própria para aceitar GET e redirecionar corretamente
    path('logout/', views.logout_view, name='logout'),
    
    # Recuperação de senha (RM)
    path('password-reset/', password_reset_views.RMPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', password_reset_views.RMPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', password_reset_views.RMPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', password_reset_views.RMPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Painel administrativo RM
    path('admin/', views.rm_admin_dashboard, name='admin_dashboard'),
    path('uso-tenants/', views.rm_tenant_usage, name='tenant_usage'),
    
    # Gestão de empresas
    path('empresas/', views.company_list, name='company_list'),
    path('empresas/criar/', views.rm_company_create, name='company_create'),
    path('empresas/<int:company_id>/editar/', views.rm_company_edit, name='company_edit'),
    path('empresas/<int:company_id>/delete/', views.rm_company_delete, name='company_delete'),
    # Portal de gestão específico da empresa (RM)
    path('empresas/<slug:company_slug>/painel/', views.rm_company_portal, name='company_portal'),
    # Checagem de login para acessar o portal de gestão
    path('empresas/<slug:company_slug>/login-check/', views.rm_company_login_check, name='company_login_check'),
    
    # Gestão de usuários (visão global)
    path('usuarios/', views.rm_user_list, name='user_list'),
    path('usuarios/quick-search/', views.rm_user_quick_search, name='user_quick_search'),
    path('usuarios/criar/', views.rm_user_create, name='user_create'),
    path('usuarios/<int:user_id>/editar/', views.rm_user_edit, name='user_edit'),
    path('usuarios/<int:user_id>/detalhes/', views.rm_user_details, name='user_details'),
    path('usuarios/<int:user_id>/enviar-email/', views.rm_user_send_email, name='user_send_email'),
    path('usuarios/<int:user_id>/enviar-ativacao/', views.rm_user_send_activation_email, name='user_send_activation'),
    path('usuarios/<int:user_id>/delete/', views.rm_user_delete, name='user_delete'),
    
    # Gestão de mapas (visão global)
    path('mapas/', views.rm_map_list, name='map_list'),
    path('mapas/por-empresa/', views.rm_maps_by_company, name='map_by_company'),
    path('mapas/download/<int:pk>/', views.rm_map_download, name='map_download'),
    path('mapas/delete/<int:pk>/', views.rm_map_delete, name='map_delete'),

    # Relatórios RM
    path('relatorios/', views.rm_reports, name='reports'),
    path('relatorios/exportar/csv/', views.rm_reports_export_csv, name='reports_export_csv'),
    
    # Sistema de tickets (RM)
    path('tickets/', views.rm_ticket_list, name='ticket_list'),
    path('tickets/<int:ticket_id>/', views.rm_ticket_detail, name='ticket_detail'),
    path('tickets/<int:ticket_id>/mensagens/', views.rm_get_new_messages, name='get_new_messages'),
    
    # Notificações de tickets
    path('notificacoes/', views.get_notifications, name='notifications'),
    path('notificacoes/contagem/', views.get_unread_count, name='notifications_count'),
    path('notificacoes/<int:notification_id>/ler/', views.mark_notification_read, name='mark_notification_read'),
    path('notificacoes/marcar-todas-lidas/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]