"""
API REST para RM Systems SaaS — queryset filtrado por tenant.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

from .models import Company, CTOMapFile
from .serializers import CompanySerializer, CTOMapFileSerializer, UserSerializer
from .permissions import IsRMAdmin, IsCompanyAdmin
from .api_permissions import IsCompanyAdminOrRM, TenantScopedPermission

User = get_user_model()


def _is_rm(user) -> bool:
    return bool(user and user.is_authenticated and (getattr(user, "is_rm_admin", False) or user.is_superuser))


class CompanyViewSet(viewsets.ModelViewSet):
    """API para gerenciamento de empresas (RM: todas; admin empresa: só a própria)."""

    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated, TenantScopedPermission]

    def get_queryset(self):
        user = self.request.user
        if _is_rm(user):
            return Company.objects.all()
        if getattr(user, "is_company_admin", False) and user.company_id:
            return Company.objects.filter(pk=user.company_id)
        return Company.objects.none()

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsAuthenticated(), IsRMAdmin()]
        if self.action in ("update", "partial_update"):
            if _is_rm(self.request.user):
                return [IsAuthenticated(), IsRMAdmin()]
            return [IsAuthenticated(), IsCompanyAdmin()]
        if self.action in ("list", "retrieve", "stats", "users"):
            return [IsAuthenticated(), IsCompanyAdminOrRM()]
        return [IsAuthenticated(), IsRMAdmin()]

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated, IsCompanyAdminOrRM])
    def stats(self, request, pk=None):
        company = self.get_object()
        from core.quotas import get_usage_summary

        stats = {
            "total_users": User.objects.filter(company=company).count(),
            "active_users": User.objects.filter(company=company, is_active=True).count(),
            "total_maps": CTOMapFile.objects.filter(company=company).count(),
            "maps_this_month": CTOMapFile.objects.filter(
                company=company,
                uploaded_at__gte=timezone.now().replace(day=1),
            ).count(),
            "last_activity": CTOMapFile.objects.filter(company=company)
            .order_by("-uploaded_at")
            .first(),
            "quotas": get_usage_summary(company),
        }
        return Response(stats)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated, IsCompanyAdminOrRM])
    def users(self, request, pk=None):
        company = self.get_object()
        users = User.objects.filter(company=company)
        serializer = UserSerializer(users, many=True, context={"request": request})
        return Response(serializer.data)


class CTOMapFileViewSet(viewsets.ModelViewSet):
    """API para gerenciamento de mapas CTO."""

    serializer_class = CTOMapFileSerializer
    permission_classes = [IsAuthenticated, TenantScopedPermission]

    def get_queryset(self):
        user = self.request.user
        if _is_rm(user):
            return CTOMapFile.objects.all()
        if user.company_id:
            return CTOMapFile.objects.filter(company_id=user.company_id)
        return CTOMapFile.objects.none()

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsCompanyAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        company = user.company if not _is_rm(user) else serializer.validated_data.get("company")
        if company:
            from core.quotas import enforce_quota

            enforce_quota(company, "maps", user=user)
        if not _is_rm(user):
            serializer.save(company=user.company, uploaded_by=user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        if not _is_rm(self.request.user):
            serializer.save(company=self.request.user.company)
        else:
            serializer.save()

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsRMAdmin])
    def by_company(self, request):
        companies = Company.objects.annotate(map_count=Count("cto_maps")).order_by("-map_count")
        data = []
        for company in companies:
            data.append(
                {
                    "company": CompanySerializer(company).data,
                    "map_count": company.map_count,
                    "last_upload": CTOMapFile.objects.filter(company=company)
                    .order_by("-uploaded_at")
                    .first(),
                }
            )
        return Response(data)

    @action(detail=False, methods=["get"])
    def recent(self, request):
        queryset = self.get_queryset().order_by("-uploaded_at")[:10]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        queryset = self.get_queryset()
        stats = {
            "total": queryset.count(),
            "this_month": queryset.filter(
                uploaded_at__gte=timezone.now().replace(day=1),
            ).count(),
            "this_week": queryset.filter(
                uploaded_at__gte=timezone.now() - timedelta(days=7),
            ).count(),
            "by_type": queryset.values("file_type")
            .annotate(count=Count("id"))
            .order_by("-count"),
        }
        return Response(stats)


class UserViewSet(viewsets.ModelViewSet):
    """API para gerenciamento de usuários."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, TenantScopedPermission]

    def get_queryset(self):
        user = self.request.user
        if _is_rm(user):
            return User.objects.all()
        if getattr(user, "is_company_admin", False) and user.company_id:
            return User.objects.filter(company_id=user.company_id)
        return User.objects.none()

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsCompanyAdmin()]
        if self.action in ("list", "retrieve", "stats", "by_company"):
            return [IsAuthenticated(), IsCompanyAdminOrRM()]
        return [IsAuthenticated(), IsCompanyAdmin()]

    def perform_create(self, serializer):
        user = self.request.user
        company = user.company if not _is_rm(user) else serializer.validated_data.get("company")
        if company:
            from core.quotas import enforce_quota

            enforce_quota(company, "users", user=user)
        if not _is_rm(user):
            serializer.save(company=user.company, role="COMPANY_USER")
        else:
            serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if not _is_rm(user):
            instance = serializer.instance
            if instance.company_id != user.company_id:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Usuário fora da sua empresa.")
            serializer.save(company=user.company)
        else:
            serializer.save()

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsRMAdmin])
    def by_company(self, request):
        companies = Company.objects.annotate(user_count=Count("users")).order_by("-user_count")
        data = []
        for company in companies:
            data.append(
                {
                    "company": CompanySerializer(company).data,
                    "user_count": company.user_count,
                    "active_users": User.objects.filter(company=company, is_active=True).count(),
                }
            )
        return Response(data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        queryset = self.get_queryset()
        stats = {
            "total": queryset.count(),
            "active": queryset.filter(is_active=True).count(),
            "inactive": queryset.filter(is_active=False).count(),
            "by_role": queryset.values("role").annotate(count=Count("id")).order_by("-count"),
            "recent_registrations": queryset.filter(
                date_joined__gte=timezone.now() - timedelta(days=30),
            ).count(),
        }
        return Response(stats)
