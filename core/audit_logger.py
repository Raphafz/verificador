"""
Sistema de Logs de Auditoria para RM Systems SaaS
"""
import logging
import json
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

# Configurar logger de auditoria
audit_logger = logging.getLogger('audit')
audit_logger.setLevel(logging.INFO)

# Handler para arquivo de auditoria (opcional)
import os
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
if os.path.exists(logs_dir):
    file_handler = logging.FileHandler(os.path.join(logs_dir, 'audit.log'))
    file_handler.setLevel(logging.INFO)
    
    # Formatter para logs estruturados
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    audit_logger.addHandler(file_handler)

class AuditLogger:
    """Classe para gerenciar logs de auditoria"""
    
    @staticmethod
    def log_user_action(user, action, details=None, ip_address=None):
        """
        Log de ações do usuário
        
        Args:
            user: Usuário que executou a ação
            action: Tipo de ação (login, logout, create_user, etc.)
            details: Detalhes adicionais da ação
            ip_address: IP do usuário
        """
        log_data = {
            'user_id': user.id if user else None,
            'username': user.username if user else 'anonymous',
            'action': action,
            'timestamp': timezone.now().isoformat(),
            'ip_address': ip_address,
            'details': details or {}
        }
        
        from .log_sanitizer import sanitize_audit_details
        if log_data.get("details"):
            log_data["details"] = sanitize_audit_details(log_data["details"])
        audit_logger.info(json.dumps(log_data, ensure_ascii=False))
    
    @staticmethod
    def log_security_event(event_type, details=None, ip_address=None):
        """
        Log de eventos de segurança
        
        Args:
            event_type: Tipo de evento (failed_login, suspicious_activity, etc.)
            details: Detalhes do evento
            ip_address: IP relacionado
        """
        log_data = {
            'event_type': event_type,
            'timestamp': timezone.now().isoformat(),
            'ip_address': ip_address,
            'details': details or {}
        }
        
        audit_logger.warning(json.dumps(log_data, ensure_ascii=False))
    
    @staticmethod
    def log_data_access(user, resource_type, resource_id, action, details=None):
        """
        Log de acesso a dados sensíveis
        
        Args:
            user: Usuário que acessou
            resource_type: Tipo do recurso (company, user, map)
            resource_id: ID do recurso
            action: Ação realizada (view, edit, delete)
            details: Detalhes adicionais
        """
        log_data = {
            'user_id': user.id,
            'username': user.username,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'action': action,
            'timestamp': timezone.now().isoformat(),
            'details': details or {}
        }
        
        from .log_sanitizer import sanitize_audit_details
        if log_data.get("details"):
            log_data["details"] = sanitize_audit_details(log_data["details"])
        audit_logger.info(json.dumps(log_data, ensure_ascii=False))

# Funções de conveniência
def log_login(user, ip_address=None):
    """Log de login bem-sucedido"""
    AuditLogger.log_user_action(
        user, 
        'login_success', 
        {'company': user.company.name if user.company else None},
        ip_address
    )

def log_logout(user, ip_address=None):
    """Log de logout"""
    AuditLogger.log_user_action(
        user, 
        'logout', 
        {'company': user.company.name if user.company else None},
        ip_address
    )

def log_failed_login(username, ip_address=None):
    """Log de tentativa de login falhada"""
    AuditLogger.log_security_event(
        'failed_login',
        {'username': username},
        ip_address
    )

def log_user_creation(creator, new_user, company=None):
    """Log de criação de usuário"""
    AuditLogger.log_user_action(
        creator,
        'user_created',
        {
            'new_user_id': new_user.id,
            'new_username': new_user.username,
            'new_user_role': new_user.role,
            'company': company.name if company else None
        }
    )

def log_user_edit(editor, edited_user, changes):
    """Log de edição de usuário"""
    AuditLogger.log_user_action(
        editor,
        'user_edited',
        {
            'edited_user_id': edited_user.id,
            'edited_username': edited_user.username,
            'changes': changes
        }
    )

def log_map_upload(user, map_file, company):
    """Log de upload de mapa"""
    AuditLogger.log_user_action(
        user,
        'map_uploaded',
        {
            'map_id': map_file.id,
            'filename': map_file.original_filename,
            'file_size': map_file.file.size if map_file.file else 0,
            'company': company.name
        }
    )

def log_data_access(user, resource_type, resource_id, action, details=None):
    """Log de acesso a dados"""
    AuditLogger.log_data_access(
        user,
        resource_type,
        resource_id,
        action,
        details
    )

def log_user_action(user, action, details=None, ip_address=None):
    """Log de ações do usuário"""
    AuditLogger.log_user_action(user, action, details, ip_address)
