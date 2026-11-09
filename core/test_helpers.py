"""Helpers para testes — Company com CNPJ válido."""
from django.utils import timezone

from .models import Company

DEFAULT_CNPJ = "11.222.333/0001-81"


def api_force_login(client, user) -> None:
    """
    Autentica APIClient e marca MFA verificado na sessão (testes com MFA_REQUIRED=True).
    """
    from core.mfa_service import mfa_required_for

    client.force_authenticate(user=user)
    if mfa_required_for(user):
        session = client.session
        session["mfa_verified_at"] = timezone.now().isoformat()
        session.save()


def make_company(name="Test Company", email="test@company.com", **kwargs):
    defaults = {
        "name": name,
        "email": email,
        "cnpj": kwargs.pop("cnpj", DEFAULT_CNPJ),
    }
    defaults.update(kwargs)
    return Company.objects.create(**defaults)
