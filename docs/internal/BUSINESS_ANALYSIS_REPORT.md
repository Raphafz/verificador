# RM Systems — Business Analysis Report

> **Arquivo interno (mai/2026).** Parte do conteúdo está desatualizada (ex.: planos em `core/plans.py`, preços em `docs/PRECOS-RM-SYSTEMS.md`). Use para contexto histórico.

## Plataforma ISP SaaS Multi-Tenant (Django)

| Campo | Valor |
|-------|--------|
| **Data** | 23 de maio de 2026 |
| **Tipo** | Due diligence técnica-comercial (read-only) |
| **Escopo** | Repositório completo — produto, arquitetura, monetização, enterprise, DevOps |
| **Classificação** | Confidencial — uso interno / investidores |

---

## Diagnóstico executivo (1 página)

O **RM Systems** não é um MVP de hobby: é um **monólito Django multi-tenant maduro** com três linhas de produto integradas (Verificador FTTH, Alertas Telegram→WhatsApp, Operações OLT/ONU), hardening de segurança/LGPD acima da média para PMEs brasileiras e documentação comercial de pricing (`VALORES-EMPRESAS.md`). A proposta de valor para **ISPs regionais** é clara e defensável.

O que **impede escala comercial imediata** não é falta de features técnicas, e sim a **lacuna entre estratégia de preço e produto**: planos e limites existem no papel, mas **não há billing, metering nem enforcement de quotas no código** — operação comercial depende de RM manual. Há também **dívida operacional** (workers Node, VPN OLT no mesmo servidor, Nginx legado vs mídia protegida) e **gaps de autorização na API DRF** que afetam confiança enterprise.

**Veredito:** produto entre **“SaaS B2B sério (Series Seed-ready com ressalvas)”** e **“plataforma vertical ISP early-enterprise”**. Adequado para **provedores pequenos e médios** (10–200 colaboradores operacionais); **grandes ISPs** exigiriam 12–24 meses de roadmap (APIs públicas, SLA, billing, multi-região, SSO).

| Indicador | Avaliação |
|-----------|-----------|
| **Score geral de maturidade** | **71 / 100** |
| **Potencial PMF (nicho ISP)** | **Alto** no segmento regional FTTH |
| **Potencial investimento** | **Moderado-alto** como vertical SaaS, não como horizontal genérico |
| **Risco founder/ops** | **Alto** em módulos OLT + alertas (complexidade operacional) |
| **Chance comercial (12 meses)** | **Boa** com vendas diretas + implantação assistida; **fraca** em self-serve puro |

---

## 1. Visão geral do produto

### 1.1 Objetivo e proposta de valor

| Dimensão | Descrição |
|----------|-----------|
| **Objetivo** | Plataforma unificada para ISPs operarem **viabilidade FTTH**, **alertas de campo via WhatsApp** e **operações em OLT** num único login multi-empresa |
| **Público-alvo primário** | Provedores regionais de internet (FTTH), equipes comerciais + NOC + engenharia de rede |
| **Público secundário** | RM Systems como operador da plataforma (painel `/rm/`), MSPs que gerenciam vários CNPJs (potencial, não first-class) |
| **Dor resolvida** | Ferramentas fragmentadas (planilhas, mapas soltos, scripts OLT, grupos Telegram manuais); falta de isolamento entre franquias/filiais |
| **Proposta de valor** | **“Um login, três operações críticas do ISP”** com isolamento por empresa e conformidade LGPD embutida |

### 1.2 Módulos e maturidade

| Módulo | Código | Maturidade estimada | Notas |
|--------|--------|---------------------|-------|
| **Verificador FTTH** | `ftth_viewer` + `CTOMapFile` | **Alta** | Core histórico; mapas, geocode, viabilidade, cache |
| **Alertas** | `alerts` + `MENSAGENS/` + `services/alert_bridge/` | **Média-alta** | Diferencial forte; depende de worker Node/Baileys |
| **OLT / ONU** | `olt_ops` | **Média** | VPN no servidor SaaS, SSH/telnet — alto custo operacional |
| **Core / RM** | `core` | **Alta** | Usuários, empresas, tickets, LGPD, MFA |
| **Billing / planos** | — | **Inexistente** | Pricing só em `VALORES-EMPRESAS.md` |

### 1.3 Product-Market Fit (PMF)

| Critério | Nota | Comentário |
|----------|------|------------|
| **PMF nicho ISP/FTTH** | **8/10** | Stack alinhada ao dia a dia do provedor brasileiro |
| **PMF telecom genérico** | **4/10** | Não cobre BSS/OSS, faturamento, CRM completo |
| **Multiempresa / multi-CNPJ** | **9/10** | Slug por tenant, middleware de módulos e acesso |
| **White-label** | **3/10** | Marca RM fixa (`SAAS_PRODUCT_NAME`); sem tema por tenant |
| **Franquia / licenciamento** | **5/10** | Arquitetura permite; falta contrato técnico (billing, domínio custom) |

**Conclusão PMF:** forte **vertical SaaS**; fraco como plataforma horizontal.

---

## 2. Análise de arquitetura

### 2.1 Organização técnica

```
┌─────────────────────────────────────────────────────────────┐
│                    Nginx / Gunicorn (VPS)                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│              Django Monolith (saas_viabilidade)                │
│  ┌─────────┐ ┌──────────────┐ ┌─────────┐ ┌──────────────┐  │
│  │  core   │ │ ftth_viewer  │ │ alerts  │ │   olt_ops    │  │
│  └─────────┘ └──────────────┘ └────┬────┘ └──────┬───────┘  │
│         PostgreSQL (Neon/VPS)      │              │          │
│         Redis (opcional)           │              │ VPN/SSH  │
└────────────────────────────────────┼──────────────┼──────────┘
                                     ▼              ▼
                            Node alert_bridge    OLTs cliente
                            MENSAGENS/Baileys
```

| Aspecto | Avaliação | Evidência |
|---------|-----------|-----------|
| **Manutenibilidade** | Boa | Apps por domínio; middlewares nomeados; design system CSS |
| **Dívida técnica** | Média | `settings_production.py` legado; `nginx.conf` vs docs deploy; pasta `desenvolvimento/` |
| **Acoplamento** | Médio | OLT e alertas acoplados à infra do mesmo host |
| **Onboarding dev** | Bom | README, `.env.example`, comandos `check_security`, testes de segurança |
| **Escala horizontal** | Limitada | Sessões Django, workers Node stateful, VPN OLT |
| **Cloud readiness** | Média | PostgreSQL gerenciado OK; sem Docker/K8s no repo |
| **Microservices readiness** | Baixa-média | Bridge já separado em Node; resto monólito |
| **APIs públicas** | Baixa | DRF interno RM; sem OpenAPI/Swagger |

### 2.2 Multi-tenant

| Mecanismo | Implementação | Risco |
|-----------|---------------|-------|
| Isolamento URL | `/<company_slug>/...` | Bom para UX; slug enumeration baixo |
| Isolamento dados | FK `company` + `get_queryset` / decorators | Bom nas views web |
| Módulos por plano | `module_verificador`, `module_alertas`, `module_olt` | **Flags booleanas**, não planos formais |
| API DRF | Filtros parciais | **Gap crítico** em `UserViewSet` / `CTOMapFileViewSet` |

### 2.3 Pontuação arquitetura

| Dimensão | Nota (0–100) |
|----------|----------------|
| Arquitetura | **78** |
| Escalabilidade | **63** |
| Segurança (código) | **74** |
| Maturidade técnica | **75** |

---

## 3. Análise B2B / Enterprise

### 3.1 Segmentos atendidos hoje

| Segmento | Pronto? | Lacunas |
|----------|---------|---------|
| **ISP pequeno (1–5 usuários)** | ✅ Sim | Onboarding ainda manual |
| **ISP médio (5–40 usuários)** | ✅ Sim | Quotas, SSO, relatórios executivos |
| **ISP grande / tier-2** | ⚠️ Parcial | SLA, HA, dedicado, auditoria SOC2 |
| **NOC 24×7** | ⚠️ Parcial | Alertas sim; sem integração SNMP/ITSM nativa |
| **Franquias / grupos** | ⚠️ Parcial | Multi-tenant ok; sem consolidação holding |
| **MSPs** | ❌ Não prioritário | Um login RM gerencia tudo |

### 3.2 Checklist enterprise

| Recurso | Status | Comentário |
|---------|--------|------------|
| RBAC | ✅ | RM / COMPANY_ADMIN / COMPANY_USER |
| MFA TOTP | ✅ | `django-otp`, lockout |
| Auditoria | ✅ | `SecurityAuditEvent`, logs sanitizados |
| LGPD | ✅ | Consentimento, export, DSR, ROPA doc |
| Trilha de sessão | ✅ | `UserSessionRecord`, idle timeout |
| Isolamento de dados | ✅ | Com ressalvas na API DRF |
| SSO/SAML | ❌ | Ausente |
| Billing automatizado | ❌ | Ausente |
| SLA contratual técnico | ❌ | Não instrumentado |

**Enterprise readiness score: 68 / 100** — pronto para **contratos PME/ médio porte** com due diligence de segurança; **não** para RFP de telecom tier-1 sem roadmap.

---

## 4. Análise de monetização

### 4.1 Modelo documentado (`VALORES-EMPRESAS.md`)

Planos fechados (BRL/mês por CNPJ):

| Plano | Preço | Perfil |
|-------|-------|--------|
| **P — Essencial** | R$ 297 | Só verificador, time mínimo |
| **M — Comercial** | R$ 497 | Mais mapas/usuários |
| **G — Operação** | R$ 797 | Verificador + alertas WhatsApp |
| **XL — Rede** | R$ 1.497 | Suite completa + OLT |

Setup único: até **R$ 690** (plano G). Desconto anual: **12%**.

> **Achado crítico (documentado no próprio arquivo):**  
> *"Limites por quantidade são comerciais até existir bloqueio automático no código."*

Isso significa **receita não protegida por produto** — cliente pode exceder uso sem upgrade automático.

### 4.2 Potencial SaaS recorrente

| Métrica | Estimativa conservadora | Estimativa otimista |
|---------|-------------------------|---------------------|
| **Ticket médio (ARPU)** | R$ 550/mês | R$ 900/mês |
| **Clientes ativos (Ano 1)** | 25–40 | 80–120 |
| **MRR** | R$ 14k – 22k | R$ 44k – 108k |
| **ARR** | R$ 168k – 264k | R$ 528k – 1,3M |

*Premissas: venda consultiva regional, não PLG self-serve.*

### 4.3 Unit economics (ordem de grandeza — Brasil B2B vertical)

| Métrica | Faixa típica | Para RM Systems |
|---------|--------------|-----------------|
| **CAC** | R$ 3.000 – 12.000 | Relacionamento, demos, implantação — **alto** |
| **Payback** | 6–14 meses | Depende de setup fee |
| **LTV (24–36 meses)** | R$ 13k – 32k | Churn técnico se OLT/alertas falharem |
| **Churn anual** | 15–25% (sem CS forte) | **Risco médio-alto** em módulo alertas |
| **Lock-in operacional** | **Médio-alto** em mapas CTO + histórico viabilidade | **Baixo** se só usar verificador |

### 4.4 Upsell e expansão de receita

| Oportunidade | Viabilidade | Esforço |
|--------------|-------------|---------|
| Upgrade P→G→XL | Alta | Baixo (comercial) — médio (produto: metering) |
| OLT como add-on | Alta | Alto (suporte VPN) |
| Chips WhatsApp extras | Alta | Médio |
| API paga (integração CRM) | Média | Alto |
| White-label para integradores | Média | Alto |
| Implantação + treinamento | **Já previsto** | Baixo |

### 4.5 Sugestão de planos (produto + comercial)

| Plano | Inclui | Preço alinhado doc | Bloqueio técnico necessário |
|-------|--------|-------------------|----------------------------|
| Starter | Verificador, 3 users, 15 mapas | R$ 297 | `max_users`, `max_maps` |
| Growth | + volume mapas/consultas | R$ 497 | meter `ViabilidadeCache` |
| Ops | + 2 chips, 3k msgs alerta | R$ 797 | worker quotas |
| Network | + OLT/VPN | R$ 1.497 | jobs/mês, OLT count |

**Monetização score: 55 / 100** — estratégia excelente no papel; **execução de produto ausente**.

---

## 5. Diferenciais competitivos

### 5.1 Funcionalidades raras no mercado ISP SMB

| Diferencial | Força | Barreira de entrada |
|-------------|-------|---------------------|
| **Suite 3-em-1** (viabilidade + alertas + OLT) | Alta | Média — integração leva tempo |
| **Bridge Telegram→WhatsApp multi-chip** | Alta | Alta — Baileys, compliance WhatsApp |
| **Geocoding com cache hash LGPD** | Média | Baixa |
| **MFA + LGPD nativos** | Média (Brasil) | Baixa |
| **Operação OLT web com VPN no SaaS** | Alta | **Muito alta** (risco também) |

### 5.2 Comparativo competitivo (simplificado)

| Concorrente / categoria | RM Systems | Gap RM | Gap concorrente |
|-------------------------|------------|--------|-----------------|
| **Planilhas + QGIS manual** | Automatizado | Custo setup | Preço |
| **ERPs ISP (IXC, Hubsoft, etc.)** | Foco operação rede | Sem billing/CRM | Menos FTTH geo |
| **Ferramentas FTTH pontuais** | Integrado alertas/OLT | Complexidade | Sem suite |
| **Zapier + bots caseiros** | Produto nativo | Manutenção WhatsApp | Sem viabilidade |

**Barreira defensiva real:** dados de mapas CTO + fluxo operacional embedado + alertas configurados — não é só código.

---

## 6. Pontos fracos de negócio

### 🔴 Críticos (impedem escala ou vendas enterprise)

| # | Fraqueza | Impacto comercial |
|---|----------|-------------------|
| 1 | **Sem billing/metering no código** | Revenue leakage; impossível self-serve |
| 2 | **API DRF com RBAC fraco** | Perde RFPs; risco incidente multi-tenant |
| 3 | **Operação OLT/VPN no servidor SaaS** | Custo suporte explosivo; responsabilidade rede cliente |
| 4 | **Dependência WhatsApp (ToS Meta)** | Risco descontinuidade; medo do comprador |
| 5 | **Nginx legado servindo `/media/` público** | Incidente de dados = fim de contrato |

### 🟠 Médios

| # | Fraqueza | Impacto |
|---|----------|---------|
| 6 | Onboarding manual (empresa, módulos, VPS) | CAC alto; não escala |
| 7 | Sem SSO / SAML | Bloqueio enterprise |
| 8 | Sem OpenAPI / integrações | Ecossistema fechado |
| 9 | `settings_production.py` divergente | Confusão deploy |
| 10 | Testes focados em segurança, poucos E2E produto | Regressão em releases |

### 🟡 Leves

| # | Fraqueza | Impacto |
|---|----------|---------|
| 11 | White-label inexistente | Perde canal revenda |
| 12 | UX com `innerHTML` em pontos críticos | Percepção “não enterprise” |
| 13 | Documentação `PLATAFORMA-UNIFICADA.md` referenciada mas ausente | Fricção onboarding dev |

---

## 7. Análise UX/UI

| Critério | Nota | Evidência |
|----------|------|-----------|
| **UX operador ISP** | **72** | Fluxos por slug; verificador map-first; tickets |
| **Curva de aprendizado** | **Média-alta** | 3 módulos distintos; OLT é nicho técnico |
| **Aparência enterprise** | **74** | `design-system.css`, dark mode, componentes DS |
| **Produtividade** | **78** | Verificador + cache viabilidade; jobs OLT ao vivo |
| **Dashboards** | **65** | Dashboard existe; analytics comercial limitado |
| **Mobile** | **60** | CSS responsivo; operação pesada em desktop |

**Pontos profissionais:** design system, portal LGPD no header, navegação por papel.

**Pontos amadores:** inconsistência entre módulos antigos/novos; modais com `innerHTML`; falta de onboarding guiado in-app.

| Dimensão | Nota |
|----------|------|
| UX | **72** |
| UI | **74** |
| Produtividade | **76** |
| Enterprise feeling | **70** |

---

## 8. DevOps / Operação

| Área | Status | Nota |
|------|--------|------|
| **Deploy VPS** | `deploy_vps.sh`, `DEPLOY.md` | Funcional, bash |
| **Docker/K8s** | Ausente | Escala limitada |
| **CI/CD** | `.github/workflows/security.yml` | Só segurança; sem deploy automático |
| **Observabilidade** | Logs rotativos, health endpoints | Sem APM obrigatório |
| **Backup** | Mencionado em docs LGPD | Não automatizado no repo |
| **DR** | Não documentado | Risco |
| **Custo infra/cliente** | Médio | OLT+alertas aumentam CPU/RAM |

**Multi-empresa na mesma VPS:** economicamente viável até ~30–50 tenants leves; módulo OLT reduz densidade.

**DevOps score: 62 / 100**

---

## 9. Segurança e compliance (visão negócio)

| Dimensão | Nota | Impacto em vendas |
|----------|------|-------------------|
| LGPD | **76** | Diferencial em contratos brasileiros |
| Segurança técnica | **74** | Due diligence passável com ressalvas |
| Auditoria | **80** | Eventos + retenção configurável |
| Prontidão jurídica | **72** | ROPA, suboperadores — falta DPA operacionalizado |

**O que impressiona investidor/cliente:** bootstrap que **impede DEBUG na VPS**, MFA, criptografia de CNPJ/tokens, portal do titular, comandos `purge_lgpd_retention`.

**O que prejudica:** gaps DRF, mídia Nginx, endpoint bridge com tokens Telegram em trânsito.

---

## 10. Análise de código e equipe

| Indicador | Avaliação |
|-----------|-----------|
| **Senioridade aparente** | **Alta** em segurança/LGPD; **média** em produto SaaS comercial |
| **Padronização** | Boa em `core/`; legado em `desenvolvimento/` |
| **Testes** | ~40+ testes segurança/LGPD; poucos testes de negócio FTTH |
| **Documentação** | Boa operacional (`docs/deploy`, LGPD); pricing excelente |
| **Contratação** | Stack Django comum no Brasil — **fácil** contratar backend |
| **Especialização** | OLT/SSH/VPN e Node Baileys — **difícil** — dependência de perfil sênior |

**Dívida técnica estimada:** 3–6 meses-dev para “SaaS comercialmente blindado” (billing + API hardening + deploy unificado).

---

## 11. Potencial comercial

### 11.1 Mercado endereçável (Brasil)

| Métrica | Ordem de grandeza |
|---------|-------------------|
| ISPs ativos (Anatel) | ~20.000+ |
| FTTH relevantes | ~3.000–8.000 |
| SAM (dispostos a pagar SaaS operação) | ~800–2.000 |
| SOM realista 3 anos | 80–250 clientes |

### 11.2 Classificação do produto

| Estágio | Corresponde? |
|---------|--------------|
| Hobby | ❌ |
| MVP | ❌ (passou) |
| **SaaS B2B sério** | ✅ |
| SaaS enterprise | ⚠️ Parcial |
| Startup escalável | ⚠️ Com ressalvas (ops-heavy) |

### 11.3 Investimento / M&A

| Ângulo | Avaliação |
|--------|-----------|
| **Aquisição estratégica** | Atrativo para ERP ISP ou integrador FTTH (acqui-hire + produto) |
| **VC growth** | Moderado — TAM vertical limitado vs horizontal |
| **Risco founder** | **Alto** se só 1 pessoa domina OLT + bridge + infra |
| **Múltiplo ARR típico (vertical SMB)** | 3×–6× ARR (pré-profit) |

---

## 12. SWOT

| **Forças** | **Fraquezas** |
|------------|---------------|
| Nicho ISP bem escolhido | Sem billing automatizado |
| 3 módulos integrados | Ops complexa (VPN, WhatsApp) |
| LGPD/segurança acima da média | API DRF imatura comercialmente |
| Pricing documentado | White-label / SSO ausentes |
| Lock-in mapas e fluxo | Escala horizontal limitada |

| **Oportunidades** | **Ameaças** |
|-------------------|-------------|
| Expansão regional LATAM ISP | Política WhatsApp / banimentos |
| Parcerias ERP ISP | Concorrentes ERP adicionam mapas |
| Metering + self-serve | Incidente segurança multi-tenant |
| API para CRMs regionais | Custos suporte OLT insustentáveis |

---

## 13. Roadmap estratégico recomendado

### 🚀 Curto prazo (0–3 meses) — “vendável e seguro”

| Prioridade | Item | Impacto |
|------------|------|---------|
| P0 | Corrigir RBAC DRF (`UserViewSet`, `CTOMapFileViewSet`) | Confiança enterprise |
| P0 | Alinhar Nginx com mídia protegida | Compliance |
| P0 | Modelo `Subscription` + limites (`max_users`, `max_maps`, flags) | Monetização |
| P1 | Dashboard de uso por tenant (metering manual→auto) | CS + upsell |
| P1 | Stripe / Asaas webhooks (Brasil) | Receita recorrente |
| P1 | Wizard onboarding empresa (checklist implantação) | Reduz CAC |

### 🏢 Médio prazo (3–9 meses) — “escala comercial”

| Item | Impacto |
|------|---------|
| Enforcement automático de quotas + emails 80% limite | Protege margem |
| SSO Google/Microsoft para empresas médias | Fecha deals |
| OpenAPI + API keys por tenant | Integrações CRM |
| Separar workers alertas em fila (Redis) | Estabilidade |
| OLT como “agent on-prem” opcional | Reduz risco VPN centralizada |
| Relatórios executivos (uso, viabilidades/mês) | Renovação |

### 🌎 Longo prazo (9–24 meses) — “enterprise / regional”

| Item | Impacto |
|------|---------|
| White-label (domínio + logo tenant) | Canal revenda |
| Multi-região / read replicas | Latência |
| ITSM (Zendesk/Jira) + webhooks alertas | NOC enterprise |
| Certificações (SOC2 type I) | Grandes contratos |
| App mobile campo (PWA) viabilidade | UX comercial |

---

## 14. Score final

| Categoria | Nota (0–100) | Peso sugerido |
|-----------|----------------|---------------|
| **Arquitetura** | 78 | 12% |
| **Segurança** | 74 | 12% |
| **LGPD** | 76 | 8% |
| **Escalabilidade** | 63 | 10% |
| **UX/UI** | 73 | 8% |
| **Produto (feature fit)** | 77 | 15% |
| **Monetização (execução)** | 55 | 15% |
| **Potencial B2B** | 72 | 10% |
| **Enterprise readiness** | 68 | 5% |
| **DevOps** | 62 | 5% |

### Score final ponderado: **71 / 100**

### Nível de maturidade

```
[ Hobby ] — [ MVP ] — [■■■■■■■□□□] SaaS B2B sério — [□□□] Enterprise
                              ▲
                         RM Systems hoje
```

### Comparação mercado

| Benchmark | Posição RM Systems |
|-----------|-------------------|
| ERP ISP médio | Mais nicho, mais profundo em FTTH/operação |
| SaaS horizontal | Perde em billing/ecossistema |
| Scripts internos ISP | Ganha em produto e LGPD |
| Startups FTTH EUA | Paridade técnica parcial; RM ganha em alertas BR |

### Chance comercial (subjetiva, 12 meses)

| Canal | Probabilidade sucesso |
|-------|----------------------|
| Venda direta regional | **70%** de fechar 20+ clientes com esforço comercial focado |
| Self-serve site | **15%** sem billing e onboarding |
| Enterprise tier-1 | **10%** sem SSO/SLA |
| Investimento seed | **55%** como vertical SaaS com tração MRR comprovada |

---

## 15. Recomendação final

### Para o fundador / operação

1. **Tratar o produto como “SaaS comercialmente incompleto”** apesar da maturidade técnica — implementar metering é tão urgente quanto features.
2. **Dobrar aposta no plano G (Operação)** como carro-chefe: maior ARPU e diferencial Telegram→WhatsApp.
3. **Isolar ou productizar o OLT** — oferecer como add-on premium com escopo de suporte claro ou agente on-prem; evita transformar o SaaS em “NOC gerenciado”.
4. **Corrigir gaps de segurança DRF antes de escalar clientes** — um incidente multi-tenant mata o posicionamento LGPD.

### Para investidores

- **Tese investível:** vertical SaaS B2B Brasil, receita recorrente, defensibilidade operacional no nicho FTTH.
- **Contraponto:** CAC alto, ops pesada, TAM limitado vs horizontal, dependência de integrações informais (WhatsApp).
- **Pedir evidência:** MRR atual, churn, tempo médio de implantação, NPS por módulo, custo suporte/tenant.

### Classificação one-liner

> **“Plataforma vertical ISP com engenharia de segurança madura e proposta comercial clara, ainda operando como software customizado premium — não como máquina de receita SaaS automatizada.”**

---

## Anexos

| Documento relacionado | Uso |
|----------------------|-----|
| `VALORES-EMPRESAS.md` | Pricing e packaging |
| `docs/ROPA.md` | Compliance |
| `docs/LGPD_IMPACT_REPORT.md` | Due diligence LGPD |
| `RELATORIO_FINAL_LGPD_SECURITY.md` | Auditoria segurança (se existir) |
| Auditoria segurança (mai/2026) | Gaps técnicos detalhados |

---

*Relatório gerado por análise estática do repositório, documentação comercial e arquitetura de código. Nenhum arquivo de aplicação foi modificado.*

*Versão 1.0 — Business Analysis — RM Systems Platform ISP*
