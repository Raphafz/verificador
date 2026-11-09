"""Billing API — stub v1 (Asaas backend existente; UI mock)."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api_permissions import RequireMfaVerified
from core.models import CompanyBilling


class BillingStubAPIView(APIView):
    permission_classes = [IsAuthenticated, RequireMfaVerified]

    def get(self, request):
        user = request.user
        company = user.company
        if not company and not user.is_rm_admin:
            return Response({"detail": "Sem empresa associada."}, status=403)

        if user.is_rm_admin and not company:
            return Response(
                {
                    "mode": "rm_operator",
                    "message": "Billing por empresa — acesse pelo tenant ou painel RM.",
                    "checkout_available": False,
                }
            )

        billing = CompanyBilling.objects.filter(company=company).first()
        plan = company.plan_code if company else "—"
        return Response(
            {
                "company_slug": company.slug,
                "plan": plan,
                "status": getattr(billing, "status", "unknown") if billing else "not_configured",
                "asaas_customer_id": getattr(billing, "asaas_customer_id", None) if billing else None,
                "checkout_available": False,
                "cta": "Falar com vendas",
                "message": "Upgrade e checkout online em breve. Contato comercial para alteração de plano.",
            }
        )
