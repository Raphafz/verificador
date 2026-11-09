"""Campo Django que persiste valores criptografados com Fernet."""
from django.db import models

from .field_encryption import decrypt_value, encrypt_value, is_encrypted


class EncryptedCharField(models.CharField):
    """CharField com criptografia transparente em repouso."""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        if is_encrypted(value):
            return decrypt_value(value)
        return value

    def get_prep_value(self, value):
        if value is None or value == "":
            return ""
        if is_encrypted(value):
            return value
        return encrypt_value(value)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs
