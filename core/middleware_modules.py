from django.core.exceptions import PermissionDenied


class SaasModuleMiddleware:
    """
    Bloqueia URLs de módulos desabilitados para a empresa do slug.
    RM/superuser ignoram a checagem.
    """

    PREFIX_MODULES = (
        ("/verificador/", "verificador"),
        ("/upload/", "verificador"),
        ("/mapas/", "verificador"),
        ("/alertas/", "alertas"),
        ("/olt/", "olt"),
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            if getattr(user, "is_rm_admin", False) or getattr(user, "is_superuser", False):
                return self.get_response(request)

            path = request.path
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2:
                slug = parts[0]
                rest = "/" + "/".join(parts[1:]) + ("/" if not path.endswith(parts[-1]) else "")
                if not rest.startswith("/"):
                    rest = "/" + "/".join(parts[1:])
                # path like /empresa-slug/verificador/...
                subpath = "/" + "/".join(parts[1:])
                if not subpath.endswith("/") and path.endswith("/"):
                    subpath += "/"

                from core.models import Company

                try:
                    company = Company.objects.get(slug=slug)
                except Company.DoesNotExist:
                    return self.get_response(request)

                if user.company_id and user.company_id != company.id:
                    return self.get_response(request)

                for prefix, module_code in self.PREFIX_MODULES:
                    if subpath.startswith(prefix) or subpath == prefix.rstrip("/"):
                        if not company.has_module(module_code):
                            raise PermissionDenied(
                                f"Módulo '{module_code}' não está habilitado para sua empresa."
                            )
                        if module_code == "alertas" and getattr(user, "role", None) == "COMPANY_USER":
                            raise PermissionDenied(
                                "O módulo Alertas (WhatsApp) é restrito ao administrador da empresa."
                            )
                        break

        return self.get_response(request)
