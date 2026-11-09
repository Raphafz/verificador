# Etapa 3 — Autorização e multi-tenant

## Vulnerabilidades corrigidas

| ID | Problema | Correção |
|----|----------|----------|
| MEDIUM | `COMPANY_USER` listava `/api/v1/users/` | `IsCompanyAdminOrRM` em list/retrieve/stats |
| MEDIUM | Escalonamento `role` → `COMPANY_ADMIN` via API | `UserSerializer.validate_role` + `perform_create` |
| HIGH | Cache geocoding clear global por qualquer user | `rm_admin_required_json` |
| HIGH | Swagger `/api/v1/docs/` aberto a admins | `RestrictedSpectacularSwaggerView` (só RM) |
| — | `by_company` sem permission explícita | `permission_classes=[IsRMAdmin]` |

## Matriz de permissões (API REST)

| Endpoint | RM | COMPANY_ADMIN | COMPANY_USER |
|----------|:--:|:-------------:|:------------:|
| `GET/POST /api/v1/companies/` | CRUD* | R (própria) | — |
| `GET .../companies/{id}/stats/` | ✓ | ✓ (tenant) | — |
| `GET .../companies/{id}/users/` | ✓ | ✓ (tenant) | — |
| `GET/POST /api/v1/users/` | CRUD* | CRUD (tenant) | — |
| `GET/POST /api/v1/maps/` | CRUD* | CRW (tenant) | R (tenant) |
| `GET .../maps/by_company/` | ✓ | — | — |
| `GET /api/v1/docs/` | ✓ | — | — |

\* RM: create/destroy companies e ações `by_company` exigem `IsRMAdmin`.

## Papel → capacidade na API

| Papel | Empresas | Usuários | Mapas | Swagger |
|-------|----------|----------|-------|---------|
| **RM** | Todas | Todos | Todos | Sim |
| **COMPANY_ADMIN** | Só a própria | Só da empresa; cria só `COMPANY_USER` | CRUD tenant | Não |
| **COMPANY_USER** | — | — | Leitura tenant | Não |

## Endpoints críticos protegidos

- `POST /{slug}/verificador/api/cache/geocoding/clear` — apenas RM
- `GET /{slug}/verificador/api/cache/geocoding/stats` — apenas RM
- `GET /api/v1/docs/` e `/api/v1/schema/` — apenas RM
- `PATCH /api/v1/users/{id}/` — sem troca de `role` (admin empresa)

## Arquivos alterados

- `core/api.py`, `core/api_permissions.py`, `core/serializers.py`
- `core/api_urls.py`, `core/api_schema_views.py`
- `core/permissions.py` (`rm_admin_required_json`)
- `ftth_viewer/views.py`
- `core/tests_security_authorization.py`, `core/tests_api_tenant.py`

---

*Etapa 4 concluída — ver `ETAPA4-API-HARDENING.md`.*
