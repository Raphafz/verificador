# RM Systems — Melhorias a fazer

| Campo | Valor |
|-------|--------|
| **Base** | [BUSINESS_ANALYSIS_REPORT.md](BUSINESS_ANALYSIS_REPORT.md) (due diligence mai/2026) |
| **Atualizado** | 23 de maio de 2026 |
| **Uso** | Marque `[x]` o que for priorizar; informe ao time o que implementar |
| **Score atual estimado** | **~74/100** (era 71 — ganhos recentes em OLT/API/Sentry) |

---

## Como ler este documento

| Símbolo | Significado |
|---------|-------------|
| **P0** | Bloqueia escala, receita ou segurança — fazer primeiro |
| **P1** | Alto impacto comercial/ops em 3–6 meses |
| **P2** | Escala e enterprise (6–12 meses) |
| **P3** | Diferencial / longo prazo (12–24 meses) |
| **Esforço** | S = dias · M = 1–3 semanas · L = 1–2 meses · XL = trimestre+ |
| **Status** | ✅ Feito · 🟡 Parcial · ⬜ Pendente |

---

## Resumo executivo

O relatório de negócio aponta um produto **tecnicamente maduro** (LGPD, MFA, 3 módulos) mas **comercialmente incompleto** (sem billing, quotas no código, onboarding manual).

**Já avançou desde o relatório** (esta branch / sessão recente):

- API DRF com escopo por tenant (empresa admin não vê outras empresas)
- OLT worker Docker + mutex VPN no host + slots paralelos
- Sentry integrado (LGPD: sem PII)
- `.env` compartilhado + `.env.local` opcional + `.gitattributes`

**Ainda falta o núcleo “máquina de receita SaaS”:** planos no banco, limites aplicados na UI/API, cobrança recorrente.

---

## Legenda de priorização sugerida

```text
Fase A (vendável seguro)     → P0 segurança/ops + metering básico
Fase B (receita recorrente)  → billing + quotas automáticas
Fase C (escala)              → SSO, API pública, agent OLT
Fase D (enterprise)          → white-label, SOC2, multi-região
```

---

## ✅ Já feito (não repetir)

| # | Item | Onde |
|---|------|------|
| A1 | API DRF: `CompanyViewSet` / mapas / usuários filtrados por tenant | `core/api.py`, `core/tests_api_tenant.py` |
| A2 | OLT: dispatcher host vs container, VPN mutex, testes | `olt_ops/dispatcher.py`, `vpn_slot.py`, `docs/deploy/OLT_WORKER.md` |
| A3 | Sentry (Error Monitoring, `send_default_pii=False`) | `saas_viabilidade/sentry_bootstrap.py`, `.env` |
| A4 | Env dupla: `.env` (repo) + `.env.local` (override) | `saas_viabilidade/env_loader.py` |
| A5 | Line endings estáveis (Windows) | `.gitattributes` |
| A6 | Rota `sentry-debug` em rotas globais (middleware) | `core/middleware_security.py` |
| A7 | Planos P/M/G/XL + enforcement de quotas no código | `core/plans.py`, `core/quotas.py`, migration `0024` |
| A8 | API DRF: object-level tenant + serializers seguros | `core/api_permissions.py`, `core/tests_api_tenant.py` |
| A9 | Nginx mídia protegida + OpenAPI + CI testes | `nginx.conf`, `core/api_urls.py`, `.github/workflows/tests.yml` |

---

## P0 — Crítico (segurança, receita, compliance)

### Monetização e produto

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P0-M01 | **Modelo `Subscription` / `Plan`** ligado a `Company` (limites: `max_users`, `max_maps`, `max_viability_month`, módulos) | L | Receita protegida | ✅ | `core/plans.py`, `Company.plan_code` + overrides |
| P0-M02 | **Enforcement de quotas** — bloquear upload, novo usuário, consulta viabilidade ao atingir limite | M | Evita revenue leakage | ✅ | `core/quotas.py` + views/API |
| P0-M03 | **Painel RM: uso por tenant** (usuários, mapas, jobs OLT, msgs alerta/mês) | M | CS + upsell | ✅ | `/rm/uso-tenants/` + link no dashboard |
| P0-M04 | **Integração cobrança** — Stripe ou Asaas (webhook → ativar/suspender empresa) | L | Recorrência real | 🟡 | `CompanyBilling` + webhook `/api/webhooks/asaas/` |

### Segurança e infra

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P0-S01 | **Nginx: remover `/media/` público** — só mídia autenticada / signed URL | S | Incidente LGPD | ✅ | `nginx.conf` proxy → Django; `docs/deploy/DEPLOY.md` |
| P0-S02 | **Auditar `settings_production.py` vs `settings.py`** — uma fonte de verdade | M | Deploy confiável | ✅ | `settings_production.py` levanta erro; usar só `settings.py` |
| P0-S03 | **CI: testes obrigatórios em PR** (não só `security.yml`) | S | Regressão | ✅ | `.github/workflows/tests.yml` |
| P0-S04 | **Rotacionar secrets** se `.env` já vazou em fork/log | S | Risco | ✅ | `docs/deploy/ROTACAO_SECRETS.md` |

### OLT / operações

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P0-O01 | **VPS produção: `OLT_EXECUTION_MODE=container`** + build imagem | S | Multi-VPN | 🟡 | Checklist em `docs/deploy/OLT_WORKER.md`; deploy manual na VPS |
| P0-O02 | **Fila de jobs OLT** (status `queued` + mensagem na UI) | M | UX quando slot ocupado | ✅ | `olt_ops/queue.py` + status `queued` |
| P0-O03 | **Documento de escopo suporte OLT** (o que está/no está no plano XL) | S | Margem / expectativa | ✅ | `docs/commercial/OLT_ESCOPO_SUPORTE.md` |

### Alertas (WhatsApp)

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P0-A01 | **Monitoramento bridge** (health + alerta se worker caiu) | S | Churn técnico | ✅ | Heartbeat + `check_bridge_health` + widget RM |
| P0-A02 | **Plano de contingência WhatsApp** (ToS Meta) na política comercial | S | Vendas | ✅ | `docs/commercial/WHATSAPP_CONTINGENCIA.md` |

---

## P1 — Alto impacto (3–6 meses)

### Comercial e onboarding

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P1-C01 | **Wizard onboarding empresa** (checklist: mapa, VPN, chip, usuários) | M | ↓ CAC | 🟡 | `onboarding_checklist` + `docs/PLATAFORMA-UNIFICADA.md` |
| P1-C02 | **E-mails automáticos 80% / 100% quota** | S | Upsell | ⬜ | Depende P0-M02 |
| P1-C03 | **Relatório mensal por empresa** (viabilidades, tickets, alertas) | M | Renovação | ⬜ | PDF ou e-mail |
| P1-C04 | **Trial 14 dias** com limites baixos + conversão | M | Aquisição | ⬜ | Flag `trial_ends_at` |

### Produto e UX

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P1-U01 | **Onboarding in-app** (tour verificador + alertas) | M | Curva aprendizado | ⬜ | 3 módulos = confusão |
| P1-U02 | **Substituir `innerHTML` crítico** por DOM seguro / templates | M | Percepção enterprise | 🟡 | Tickets chat + `static/js/dom-safe.js` |
| P1-U03 | **Dashboard executivo** (KPIs: viabilidades/mês, mapas, jobs) | L | Renovação | ⬜ | Hoje dashboard básico |
| P1-U04 | **PWA / mobile** para verificador em campo | L | Comercial externo | ⬜ | Score mobile 60 no relatório |

### Técnico

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P1-T01 | **OpenAPI (Swagger)** para `/api/v1/` | M | Integrações CRM | ✅ | `/api/v1/docs/` (drf-spectacular) |
| P1-T02 | **API keys por tenant** (leitura viabilidade / mapas) | L | Ecossistema | ⬜ | Rate limit por key |
| P1-T03 | **Testes E2E** (login empresa → upload mapa → viabilidade) | L | Release seguro | ⬜ | Playwright |
| P1-T04 | **Testes FTTH** (geocode, viabilidade, cache) | M | Core do produto | ⬜ | Poucos hoje |
| P1-T05 | **Redis obrigatório em produção** (cache, fila, bridge nonce) | S | Escala | 🟡 | `.env` tem flag off em dev |
| P1-T06 | **Fila Redis para alert bridge** (desacoplar Node do runserver) | M | Estabilidade | ⬜ | Worker sempre on na VPS |

### OLT

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P1-O01 | **Agent on-prem OLT** (serviço na rede do ISP, SaaS só orquestra) | XL | ↓ suporte VPN | ⬜ | Roadmap relatório |
| P1-O02 | **UI: modo execução OLT** (host/container) no admin empresa | S | Ops | 🟡 | Model `CompanyOltExecutionConfig` existe |
| P1-O03 | **Limite jobs OLT/mês por plano** | S | Margem XL | ⬜ | Depende P0-M01 |

---

## P2 — Escala e enterprise (6–12 meses)

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P2-E01 | **SSO Google / Microsoft** (OAuth2 / SAML) | L | Deals médios | ⬜ | Bloqueio enterprise |
| P2-E02 | **SLA instrumentado** (uptime, tempo resposta health) | M | Contratos | ⬜ | Statuspage ou interno |
| P2-E03 | **Backup automatizado** (DB + media) + teste restore | M | DR | ⬜ | Mencionado LGPD, não no repo |
| P2-E04 | **CI/CD deploy** (GitHub Actions → VPS) | M | Velocidade | ⬜ | Só security workflow hoje |
| P2-E05 | **Docker Compose produção** (Django + Redis + bridge + workers) | L | Ops | 🟡 | Só imagem OLT worker |
| P2-E06 | **Holding / multi-CNPJ** (visão consolidada RM) | L | Franquias | ⬜ | Arquitetura permite |
| P2-E07 | **DPA operacionalizado** com suboperadores (Neon, Sentry, ORS) | S | Jurídico | ⬜ | `docs/SUBOPERADORES-LGPD.md` |
| P2-E08 | **Canal oficial WhatsApp Business API** (alternativa Baileys) | XL | Risco Meta | ⬜ | Custo maior, mais estável |

---

## P3 — Longo prazo (12–24 meses)

| ID | Melhoria | Esforço | Impacto | Status | Notas |
|----|----------|---------|---------|--------|-------|
| P3-L01 | **White-label** (logo, cores, domínio custom por tenant) | XL | Revenda | ⬜ | Score 3/10 hoje |
| P3-L02 | **Multi-região / read replica** | XL | Latência LATAM | ⬜ | |
| P3-L03 | **ITSM** (webhooks alertas → Zendesk/Jira) | L | NOC enterprise | ⬜ | |
| P3-L04 | **SOC 2 Type I** | XL | Tier-1 | ⬜ | |
| P3-L05 | **Self-serve completo** (cadastro + pagamento + provision) | XL | PLG | ⬜ | 15% chance sem billing |

---

## Dívida técnica e higiene (rápido)

| ID | Melhoria | Esforço | Status |
|----|----------|---------|--------|
| D01 | Remover ou arquivar pasta `desenvolvimento/` legada | S | ✅ | `archive/legacy-desktop-tools/` |
| D02 | Criar `docs/PLATAFORMA-UNIFICADA.md` | S | ✅ |
| D03 | Unificar `MENSAGENS/` → só `services/alert_bridge/` | M | ⬜ |
| D04 | Consolidar commits (OLT / Sentry / infra) em PRs separados | S | ⬜ |
| D05 | Ampliar cobertura: `permissions.py`, middlewares, forms críticos | M | ⬜ |

---

## Matriz decisão (para você marcar)

Copie os IDs na resposta, ex.: *"Fazer P0-M01, P0-M02, P0-S01, P1-T04"*.

### Pacote recomendado **Fase A** (8–12 semanas-dev, 1 dev)

```
P0-M01, P0-M02, P0-M03, P0-S01, P0-S02, P0-O01, P0-O02, P1-T04, P1-T05
```

**Resultado:** vendável com limites reais, deploy seguro, OLT estável em multi-tenant.

### Pacote recomendado **Fase B** (receita)

```
P0-M04, P1-C02, P1-C01, P1-T01, P1-U03
```

**Resultado:** cobrança recorrente + onboarding + visibilidade de uso.

### Pacote **mínimo segurança** (se tempo curto)

```
P0-S01, P0-S03, P0-S04
```

*(P0-S04 API DRF já feito — substituir por revisão Nginx + CI)*

---

## Impacto esperado nos scores (estimativa)

| Categoria | Relatório | Após Fase A | Após Fase A+B |
|-----------|-----------|-------------|---------------|
| Monetização | 55 | 62 | **78** |
| Enterprise | 68 | 72 | 76 |
| Escalabilidade | 63 | **72** | 75 |
| DevOps | 62 | 68 | 74 |
| **Global** | **71** | **~76** | **~82** |

---

## Riscos se NÃO fizer

| Ignorar | Consequência |
|---------|--------------|
| P0-M01/M02 | Cliente usa plano P com volume de XL; margem negativa |
| P0-S01 | Vazamento mapas CTO via URL pública |
| P0-O01 | Dois ISPs com VPN = falhas intermitentes na VPS |
| P0-A01 | Alertas param silenciosamente; churn |
| P1-E01 | Perde ISP médio que exige login corporativo |

---

## Próximo passo

1. Marque os IDs deste arquivo que quer implementar.  
2. Indique prazo (ex.: “Fase A em 1 mês”).  
3. O time implementa na ordem P0 → P1, atualizando a coluna **Status** aqui.

---

*Documento derivado de BUSINESS_ANALYSIS_REPORT.md v1.0, atualizado com o estado do repositório em 23/05/2026.*
