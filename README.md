# RM Systems — Plataforma ISP (SaaS)

[![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-obrigatório-4169E1?logo=postgresql)](https://www.postgresql.org/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)](https://www.python.org/)

SaaS **multi-tenant** para provedores de internet (ISPs): verificação de viabilidade FTTH, alertas operacionais (Telegram → WhatsApp) e operações em OLT/ONU — em um único login por empresa (CNPJ).

| Documento | Descrição |
|-----------|-----------|
| [docs/DOCUMENTACAO-TECNICA.md](docs/DOCUMENTACAO-TECNICA.md) | Arquitetura, APIs, modelos, segurança, deploy (referência completa) |
| [docs/PLATAFORMA-UNIFICADA.md](docs/PLATAFORMA-UNIFICADA.md) | Visão dos três módulos e mapa do código |
| [docs/README.md](docs/README.md) | Índice de toda a documentação |
| [docs/deploy/DEPLOY.md](docs/deploy/DEPLOY.md) | Deploy em VPS (Nginx + Gunicorn) |

## Autoria e uso

Projeto desenvolvido por **Raphael Ferraz** em parceria com **[castrox-dev](https://github.com/castrox-dev)**.

> ⚠️ **Uso comercial não autorizado.** Este projeto **não autoriza** o uso para comercialização — é proibido vender, sublicenciar, hospedar como serviço pago ou usar este código/produto com fins comerciais sem autorização expressa dos autores.

---

## Objetivo

Centralizar ferramentas que ISPs regionais usam de forma fragmentada (planilhas, scripts desktop, bots isolados) em uma plataforma web com:

- **Isolamento por tenant** (empresa/slug)
- **Planos comerciais** com quotas (P / M / G / XL)
- **Conformidade LGPD** (consentimento, portal do titular, retenção)
- **Segurança enterprise** (MFA, CSP, mídia protegida, criptografia de segredos)

---

## Módulos do produto

| Módulo | URL (tenant) | Função |
|--------|----------------|--------|
| **Verificador FTTH** | `/{slug}/verificador/` | Mapas CTO, geocoding, viabilidade por distância |
| **Alertas** | `/{slug}/alertas/` | Bridge Telegram → WhatsApp (worker Node) |
| **OLT / ONU** | `/{slug}/olt/` | Cadastro OLT, VPN, jobs CLI Huawei/ZTE |

Painel **RM** (operador da plataforma): `/rm/` — empresas, usuários globais, mapas, tickets, relatórios.

---

## Stack tecnológica

| Camada | Tecnologia |
|--------|------------|
| Backend | Django 5.2, Python 3.12+ |
| API | Django REST Framework + OpenAPI (`drf-spectacular`) |
| Banco | PostgreSQL (`DATABASE_URL` obrigatória) |
| Cache / rate limit | Redis (opcional, recomendado em produção) |
| Auth | Sessões Django + `django-otp` (TOTP MFA) |
| Frontend | Templates Django + JavaScript vanilla + CSS (design system próprio) |
| E-mail | Resend (`core.email.resend_backend`) |
| Billing | Asaas (webhook `/api/webhooks/asaas/`) |
| Workers | `services/alert_bridge` (Node), `services/olt_worker` (Docker) |
| Produção | Gunicorn, WhiteNoise, Nginx |
| Monitoramento | Sentry, logs estruturados |

**Não há** frontend React/Vue separado nem build Webpack — o UI é server-rendered com assets em `static/`.

---

## Arquitetura (resumo)

```
                    ┌─────────────────────────────────────┐
                    │           Nginx (HTTPS)              │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │     Gunicorn → Django (monólito)     │
                    │  core │ ftth_viewer │ alerts │ olt  │
                    └──────────────┬──────────────────────┘
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
    ┌──────▼──────┐        ┌───────▼───────┐       ┌───────▼────────┐
    │ PostgreSQL  │        │    Redis      │       │ Alert Bridge   │
    │  (tenant)   │        │ cache/limit   │       │ (Node :3921)   │
    └─────────────┘        └───────────────┘       └────────────────┘
                                                           │
                                                   ┌───────▼────────┐
                                                   │ OLT Worker     │
                                                   │ (Docker/job)   │
                                                   └────────────────┘
```

Detalhes: [docs/DOCUMENTACAO-TECNICA.md#2-arquitetura-do-sistema](docs/DOCUMENTACAO-TECNICA.md).

---

## Estrutura de pastas

```
Saas-Verificador-de-Viabilidade/
├── saas_viabilidade/      # Settings, URLs raiz, bootstrap segurança, runserver custom
├── core/                  # Tenant, usuários, tickets, LGPD, billing, API DRF, middlewares
├── ftth_viewer/           # Verificador (mapa, viabilidade, caches)
├── alerts/                # Módulo alertas + API interna para worker
├── olt_ops/               # OLT, VPN, jobs ONU
├── templates/             # HTML (rm/, company/, legal/, docs/)
├── static/                # CSS, JS, imagens, ftth_viewer/
├── services/
│   ├── alert_bridge/      # Worker Node Telegram→WhatsApp
│   └── olt_worker/          # Imagem Docker para jobs OLT
├── docs/                  # Documentação (deploy, LGPD, preços, técnica)
├── scripts/               # Cron LGPD, segurança, build worker
├── archive/               # Código legado (desktop tools)
├── manage.py
├── requirements.txt
├── deploy_vps.sh          # Deploy incremental na VPS
├── nginx.conf
└── gunicorn.service
```

---

## Pré-requisitos

- Python **3.12+**
- **PostgreSQL** 14+ (local ou Neon/cloud)
- **Node.js 18+** (apenas se `RUN_ALERT_BRIDGE=true` em dev)
- **Redis** (opcional em dev; recomendado em produção)
- **Docker** (opcional — jobs OLT em `OLT_EXECUTION_MODE=container`)

---

## Instalação (desenvolvimento)

### 1. Clonar e entrar no projeto

```bash
git clone <url-do-repositorio>
cd Saas-Verificador-de-Viabilidade
```

### 2. Ambiente virtual e dependências

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Variáveis de ambiente

```bash
cp .env.example .env
```

Edite `.env` — mínimo obrigatório:

```env
SECRET_KEY=<gere-uma-chave-forte>
DEBUG=True
DATABASE_URL=postgresql://postgres:senha@localhost:5432/saas_viabilidade
ALLOWED_HOSTS=127.0.0.1,localhost
FIELD_ENCRYPTION_KEY=<Fernet-key>
```

Gerar chaves:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Lista completa de variáveis: [docs/DOCUMENTACAO-TECNICA.md#15-variáveis-de-ambiente](docs/DOCUMENTACAO-TECNICA.md).

### 4. Banco de dados

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Executar

```bash
python manage.py runserver
```

O comando `runserver` customizado (`saas_viabilidade/management/commands/runserver.py`) pode subir o **Alert Bridge** automaticamente quando `DEBUG=True` e `RUN_ALERT_BRIDGE=true`.

| Destino | URL |
|---------|-----|
| Login RM | http://127.0.0.1:8000/rm/login/ |
| Empresa (exemplo) | http://127.0.0.1:8000/{slug}/login/ |
| API REST | http://127.0.0.1:8000/api/v1/ |
| Swagger | http://127.0.0.1:8000/api/v1/docs/ |
| Health | http://127.0.0.1:8000/health/ |

---

## Scripts e comandos úteis

| Comando | Uso |
|---------|-----|
| `python manage.py runserver` | Servidor dev (+ bridge opcional) |
| `python manage.py migrate` | Aplicar migrações |
| `python manage.py collectstatic --noinput` | Coletar estáticos (produção) |
| `python manage.py check_security --deploy` | Checklist segurança |
| `python manage.py onboarding_checklist` | Checklist onboarding empresa |
| `python manage.py test_resend_email --list` | Testar templates de e-mail |
| `python manage.py purge_lgpd_retention` | Retenção LGPD (cron) |
| `python manage.py purge_geocoding_cache` | Limpar cache FTTH |
| `python manage.py test` | Suite de testes |

Deploy VPS:

```bash
./deploy_vps.sh
```

Guia completo: [docs/deploy/DEPLOY.md](docs/deploy/DEPLOY.md).

---

## Build e produção

Não há build de frontend separado. Em produção:

1. `collectstatic` (WhiteNoise + manifest)
2. Gunicorn via `gunicorn_config.py` / systemd `gunicorn.service`
3. Nginx como reverse proxy (`nginx.conf`)
4. PostgreSQL + Redis na VPS ou gerenciados
5. Cron: `scripts/cron-lgpd-retention.sh`, `scripts/cron-purge-caches.sh`

```bash
export VPS_ENVIRONMENT=true
export DEBUG=False
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

**Mídia:** mapas CTO **não** devem ser servidos como `alias` público no Nginx — o projeto usa proxy autenticado (`core/media_protected.py`).

---

## Autenticação e papéis

| Papel | Código | Acesso |
|-------|--------|--------|
| Admin RM | `RM` | `/rm/*`, todas empresas, API global |
| Admin empresa | `COMPANY_ADMIN` | Gestão usuários, alertas, mapas, tickets |
| Usuário empresa | `COMPANY_USER` | Verificador e upload (sem alertas/OLT admin) |

MFA TOTP obrigatório para RM quando `MFA_REQUIRED=true`. Detalhes: [docs/DOCUMENTACAO-TECNICA.md#6-autenticação-permissões-e-multi-tenant](docs/DOCUMENTACAO-TECNICA.md).

---

## Planos comerciais

Definidos em `core/plans.py` (espelham [docs/PRECOS-RM-SYSTEMS.md](docs/PRECOS-RM-SYSTEMS.md)):

| Plano | Módulos | Preço sugerido |
|-------|---------|----------------|
| P | Verificador | R$ 297/mês |
| M | Verificador | R$ 497/mês |
| G | Verificador + Alertas | R$ 797/mês |
| XL | Completo (+ OLT) | R$ 1.497/mês |

Quotas aplicadas via `core/quotas.py` quando `Company.quota_enforcement=True`.

---

## Telas principais

| Área | Telas |
|------|--------|
| **RM** | Login, dashboard, CRUD empresas (módulos/plano), usuários globais, mapas, tickets, relatórios CSV, MFA |
| **Empresa** | Login, hub de módulos, painel, upload de mapas, lista/histórico mapas, verificador (mapa interativo), usuários, tickets (chat AJAX), relatórios |
| **Alertas** | Config bridge Telegram, linhas WhatsApp, QR/pareamento |
| **OLT** | VPN, cadastro OLT, job listar/excluir ONUs, log ao vivo |
| **LGPD** | Consentimento, portal `/meus-dados/`, export ZIP, DPO |
| **Público** | Termos, privacidade, cookies, FAQ, ajuda |

UI: tema claro/escuro (`static/js/dark-mode.js`), design system em `static/css/design-system.css` e `platform.css`.

---

## Testes e CI

```bash
python manage.py test core.tests_quotas core.tests_api_tenant olt_ops.tests_vpn_slot olt_ops.tests_dispatcher
```

GitHub Actions (`.github/workflows/tests.yml`): Python 3.12, SQLite apenas na CI (produção exige PostgreSQL).

---

## Contribuição

1. Crie uma branch a partir de `main`
2. Siga convenções existentes (decorators `company_access_required`, quotas, sem expor PII em logs)
3. Rode testes e `python manage.py check_security --deploy` antes do PR
4. Documente endpoints novos no Swagger (`drf-spectacular`) ou em `docs/DOCUMENTACAO-TECNICA.md`

Backlog interno: [docs/internal/MELHORIAS_A_FAZER.md](docs/internal/MELHORIAS_A_FAZER.md).

---

## Boas práticas do projeto

- **Tenant first:** toda query de dados de cliente filtra por `company_id` / `request.company`
- **Segredos:** CNPJ, tokens Telegram, senhas OLT/VPN em `EncryptedCharField` + `FIELD_ENCRYPTION_KEY`
- **Uploads:** validação de tipo/tamanho; ClamAV opcional (`UPLOAD_ANTIVIRUS_ENABLED`)
- **CSP:** nonces em produção (`CSP_STRICT=true`); evitar inline script sem nonce
- **Não commitar** `.env` com segredos reais — use `.env.example` e `.env.local` (gitignored)
- **Workers:** rotacionar `ALERT_BRIDGE_API_TOKEN` / `BRIDGE_HMAC_SECRET` com `rotate_bridge_credentials`

---

## Licença

Código proprietário RM Systems. Defina termos de uso com o mantenedor antes de redistribuir.

---

## Suporte

- Documentação técnica: [docs/DOCUMENTACAO-TECNICA.md](docs/DOCUMENTACAO-TECNICA.md)
- E-mail (configurável): `EMAIL_SUPPORT_EMAIL` / `DPO_EMAIL` no `.env`
- Issues no repositório Git (se habilitado)

**Desenvolvido para ISPs que precisam de viabilidade, alertas e operação OLT no mesmo lugar.**
