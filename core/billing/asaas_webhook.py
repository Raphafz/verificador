"""Webhook Asaas — ativa/suspende empresa conforme pagamento."""
from __future__ import annotations

import json
import logging
import secrets

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import CompanyBilling

logger = logging.getLogger(__name__)


def _webhook_token_ok(request) -> bool:
    expected = getattr(settings, "ASAAS_WEBHOOK_TOKEN", "").strip()
    if not expected:
        return False
    if request.GET.get("token"):
        logger.warning("Asaas webhook: token via query string rejeitado")
        return False
    provided = (
        request.headers.get("asaas-access-token")
        or request.headers.get("X-Asaas-Token")
        or ""
    ).strip()
    return bool(provided) and secrets.compare_digest(provided, expected)


def _find_billing(payload: dict) -> CompanyBilling | None:
    payment = payload.get("payment") or {}
    subscription = payload.get("subscription") or {}
    customer_id = (
        payment.get("customer")
        or subscription.get("customer")
        or payload.get("customer")
        or ""
    )
    subscription_id = payment.get("subscription") or subscription.get("id") or ""
    if customer_id:
        billing = (
            CompanyBilling.objects.filter(asaas_customer_id=customer_id)
            .select_related("company")
            .first()
        )
        if billing:
            return billing
    if subscription_id:
        return (
            CompanyBilling.objects.filter(asaas_subscription_id=subscription_id)
            .select_related("company")
            .first()
        )
    return None


@csrf_exempt
@require_POST
def asaas_webhook(request):
    if not getattr(settings, "ASAAS_WEBHOOK_TOKEN", "").strip():
        logger.error("Asaas webhook: ASAAS_WEBHOOK_TOKEN não configurado")
        return JsonResponse({"error": "Webhook não configurado"}, status=503)

    if not _webhook_token_ok(request):
        logger.warning("Asaas webhook: token inválido")
        return HttpResponseForbidden("Forbidden")

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    event = (payload.get("event") or "").upper()
    billing = _find_billing(payload)

    if not billing:
        logger.info("Asaas webhook sem billing local: event=%s", event)
        return JsonResponse({"ok": True})

    billing.last_webhook_at = timezone.now()
    billing.last_webhook_event = event[:64]
    billing.save(update_fields=["last_webhook_at", "last_webhook_event", "updated_at"])

    if event in ("PAYMENT_RECEIVED", "PAYMENT_CONFIRMED", "PAYMENT_RECEIVED_IN_CASH"):
        billing.apply_payment_received()
    elif event in ("PAYMENT_OVERDUE", "PAYMENT_DELETED"):
        billing.apply_payment_overdue()
    elif event in ("SUBSCRIPTION_DELETED", "SUBSCRIPTION_INACTIVATED"):
        billing.apply_subscription_cancelled()
    else:
        logger.debug("Asaas webhook evento não mapeado: %s", event)

    payload = {"ok": True}
    if settings.DEBUG:
        payload["event"] = event
        payload["company"] = billing.company.slug
    return JsonResponse(payload)
