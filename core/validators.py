from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import re
import string

class ComplexPasswordValidator:
    """
    Validador de senha complexa para maior segurança
    """
    
    def __init__(self, min_length=12, require_uppercase=True, require_lowercase=True, 
                 require_digits=True, require_symbols=True, max_similarity=0.7):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_symbols = require_symbols
        self.max_similarity = max_similarity
    
    def validate(self, password, user=None):
        if not password:
            raise ValidationError(_("Senha é obrigatória"))
        
        # Verificar comprimento mínimo
        if len(password) < self.min_length:
            raise ValidationError(
                _("A senha deve ter pelo menos %(min_length)d caracteres."),
                code='password_too_short',
                params={'min_length': self.min_length},
            )
        
        # Verificar caracteres maiúsculos
        if self.require_uppercase and not any(c.isupper() for c in password):
            raise ValidationError(
                _("A senha deve conter pelo menos uma letra maiúscula."),
                code='password_no_upper',
            )
        
        # Verificar caracteres minúsculos
        if self.require_lowercase and not any(c.islower() for c in password):
            raise ValidationError(
                _("A senha deve conter pelo menos uma letra minúscula."),
                code='password_no_lower',
            )
        
        # Verificar dígitos
        if self.require_digits and not any(c.isdigit() for c in password):
            raise ValidationError(
                _("A senha deve conter pelo menos um número."),
                code='password_no_digit',
            )
        
        # Verificar símbolos
        if self.require_symbols and not any(c in string.punctuation for c in password):
            raise ValidationError(
                _("A senha deve conter pelo menos um símbolo especial."),
                code='password_no_symbol',
            )
        
        # Verificar sequências comuns
        if self._has_common_sequences(password):
            raise ValidationError(
                _("A senha não pode conter sequências comuns como '123' ou 'abc'."),
                code='password_common_sequence',
            )
        
        # Verificar palavras comuns
        if self._has_common_words(password):
            raise ValidationError(
                _("A senha não pode conter palavras comuns."),
                code='password_common_word',
            )
        
        # Verificar similaridade com dados do usuário
        if user and self._is_too_similar(password, user):
            raise ValidationError(
                _("A senha é muito similar aos seus dados pessoais."),
                code='password_too_similar',
            )
    
    def get_help_text(self):
        help_texts = []
        
        if self.min_length:
            help_texts.append(f"Pelo menos {self.min_length} caracteres")
        
        if self.require_uppercase:
            help_texts.append("Uma letra maiúscula")
        
        if self.require_lowercase:
            help_texts.append("Uma letra minúscula")
        
        if self.require_digits:
            help_texts.append("Um número")
        
        if self.require_symbols:
            help_texts.append("Um símbolo especial")
        
        return "A senha deve conter: " + ", ".join(help_texts) + "."
    
    def _has_common_sequences(self, password):
        """Verificar sequências comuns"""
        common_sequences = [
            '123', '234', '345', '456', '567', '678', '789', '890',
            'abc', 'bcd', 'cde', 'def', 'efg', 'fgh', 'ghi', 'hij',
            'qwe', 'wer', 'ert', 'rty', 'tyu', 'yui', 'uio', 'iop',
            'asd', 'sdf', 'dfg', 'fgh', 'ghj', 'hjk', 'jkl', 'kl;',
            'qaz', 'wsx', 'edc', 'rfv', 'tgb', 'yhn', 'ujm', 'ik,',
        ]
        
        password_lower = password.lower()
        for sequence in common_sequences:
            if sequence in password_lower:
                return True
        return False
    
    def _has_common_words(self, password):
        """Verificar palavras comuns"""
        common_words = [
            'password', 'senha', '123456', 'admin', 'user', 'login',
            'welcome', 'bemvindo', 'test', 'teste', 'demo', 'sample',
            'company', 'empresa', 'business', 'negocio', 'system',
            'sistema', 'database', 'banco', 'server', 'servidor'
        ]
        
        password_lower = password.lower()
        for word in common_words:
            if word in password_lower:
                return True
        return False
    
    def _is_too_similar(self, password, user):
        """Verificar similaridade com dados do usuário"""
        user_data = [
            user.username,
            user.first_name,
            user.last_name,
            user.email.split('@')[0] if user.email else '',
        ]
        
        password_lower = password.lower()
        for data in user_data:
            if data and len(data) > 2:
                if data.lower() in password_lower:
                    return True
        return False

