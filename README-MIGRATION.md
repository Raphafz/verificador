# Migração React SPA (Strangler Fig)



Migração incremental do front-end Django SSR para React (Vite + TypeScript + Tailwind + shadcn/ui).



## Modos



| `FRONTEND_MODE` | Comportamento |

|-----------------|---------------|

| `hybrid` (padrão) | SSR + SPA convivem |

| `spa` | Rotas migradas redirecionam para `FRONTEND_URL` |

| `ssr` | Apenas Django templates |



## Status da migração



### Concluído (React)



- Landing, login RM/tenant, MFA (verify + setup), troca de senha

- Password reset (solicitar + confirmar), ativação de conta

- AppShell, dark mode, dashboards RM/tenant com stats reais

- Listagens: empresas, usuários, mapas (RM + tenant)

- Perfil: sessões JWT + dispositivos confiáveis MFA

- Billing stub

- Hub de módulos com links SSR para FTTH/Alertas/OLT



### Permanece SSR (próximas fases)



- Mapa FTTH (`/{slug}/verificador/`) — Fase 3 (react-leaflet)

- Alertas, OLT — Fase 4

- CRUD avançado (criar empresa, upload mapas, tickets, relatórios)

- Billing real (Stripe) — Fase 5



## Rotas SPA



| Rota | Descrição |

|------|-----------|

| `/` | Landing |

| `/rm/login` | Login operador RM |

| `/:slug/login` | Login empresa |

| `/mfa`, `/mfa/setup` | MFA |

| `/change-password` | Troca obrigatória |

| `/rm/password-reset` | Reset senha RM |

| `/:slug/password-reset` | Reset senha tenant |

| `/ativar-conta/:token` | Ativação |

| `/rm/dashboard` | Dashboard RM |

| `/rm/empresas`, `/rm/usuarios`, `/rm/mapas` | Admin RM |

| `/:slug/hub`, `/:slug/dashboard` | Tenant |

| `/:slug/usuarios`, `/:slug/mapas` | Admin tenant |

| `/*/perfil` | Sessões e segurança |

| `/*/billing` | Billing stub |



## Backend API (`/api/v1/`)



Auth JWT, MFA, sessões, ViewSets `companies`, `users`, `maps`, contexto tenant, FTTH wrappers.



Ver `docs/MIGRATION_PHASE0.md` para detalhes da Fase 0.



## Frontend (`/frontend`)



```bash

cd frontend

npm install

npm run dev    # http://localhost:5173

npm run build  # dist/ para produção

```



Proxy Vite: `/api` → `http://127.0.0.1:8000`



### Variáveis (.env)



```env

FRONTEND_MODE=hybrid

FRONTEND_URL=http://localhost:5173

CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

JWT_ACCESS_MINUTES=15

JWT_REFRESH_DAYS=7

```



### Rodar local



Terminal 1: `python manage.py runserver`  

Terminal 2: `cd frontend && npm run dev`



### Produção (SPA)



1. `cd frontend && npm run build`

2. Servir `frontend/dist/` via nginx/CDN na mesma origem ou subdomínio

3. Definir `FRONTEND_MODE=spa` e `FRONTEND_URL=https://app.exemplo.com`

4. Django continua como API em `/api/v1/`



## Próximas fases



- **Fase 3:** FTTH mapa em react-leaflet

- **Fase 4:** Alertas + OLT

- **Fase 5:** Billing real + self-signup

