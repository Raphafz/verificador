# Frontend Refactor TODO — RM Systems UI v2

Checklist para conclusão da remodelação visual. Itens marcados com `[x]` foram entregues nesta fase.

---

## Fase 0 — Fundação

- [x] Mapear templates (`templates/`, `core/templates/`)
- [x] Mapear CSS/JS estáticos
- [x] Extrair paleta de `logos-rmsys/`
- [x] Criar pasta `static/css/ds/` (variables, theme, animations, components, layout, utilities)
- [x] Integrar DS em `base.html`, `base_minimal.html`, `login.html`
- [x] Documentar em `UI_REDESIGN_REPORT.md` e `DESIGN_SYSTEM.md`

---

## Fase 1 — Tema e motion global

- [x] Dark mode enterprise (`#070d18` base)
- [x] Transição suave troca de tema (`rm-theme-transition`)
- [x] `rm-ui.js` (partículas, command palette shell, sidebar collapse)
- [x] Scrollbar premium
- [x] Mesh de fundo em `.main-container`
- [ ] Modo `auto` explícito no theme toggle (light / dark / system)
- [ ] Sincronizar `docs_base.html` e páginas legais com stack ds/

---

## Fase 2 — Layout shell

- [x] Topbar premium (CSS)
- [x] Sidebar indicador ativo + glow dark
- [x] Sidebar colapsável desktop
- [x] Breadcrumbs dinâmicos via template tag Django (`{% rm_breadcrumbs %}`)
- [x] User dropdown na topbar (avatar + links Meus dados / Sair)
- [ ] Notificações bell (UI only)
- [ ] Search global na topbar (wireframe)

---

## Fase 3 — Componentes por página

### Dashboards

- [x] Reforço hover KPI `rm-dashboard.css`
- [ ] `company-dashboard.css` — alinhar tokens ds
- [ ] Gráficos Chart.js — tema dark automático nas cores
- [ ] Skeleton em cards durante load AJAX

### Listagens (users, tickets, maps, companies)

- [x] Envolver tabelas em `.rm-table-wrap` (RM/company tickets, users, maps, OLT, admin maps)
- [ ] Barra de filtros com `.rm-search`
- [ ] Paginação estilo premium (sem quebrar querystring)
- [x] Empty states `.rm-empty` (partial `includes/rm_empty_state.html` — várias listas)

### Formulários

- [x] Aplicar `.rm-field` em forms company (users) + CSS global `.saas-page .form-group`
- [ ] Floating labels nos forms principais
- [ ] Toggle switches custom (alertas, MFA)

### Modais

- [ ] Revisar animação Bootstrap modal + backdrop blur
- [ ] Confirm dialogs consistentes

### Login / auth

- [x] Dark login alinhado à paleta RM
- [ ] Unificar variáveis `--img-*` → `--rm-*` em `login.css`
- [ ] Hero animado leve (sem impacto performance mobile)
- [ ] MFA pages (`mfa_*.html`) — stack ds completa

---

## Fase 4 — Módulos específicos

- [ ] `ftth_viewer` — importar tokens; theme toggle unificado
- [ ] `olt_ops/base_olt.html` — herdar melhorias sidebar
- [ ] `tickets-page.css` — badges e thread premium
- [ ] `upload-page.css` — dropzone glow + skeleton
- [ ] `verificador.css` — mapa e cards CTO
- [ ] Emails transacionais — já separados; revisar contraste

---

## Fase 5 — UX avançada

- [x] Command palette UI (`Ctrl+K`)
- [x] Command palette: rotas por perfil (JSON em `base.html`)
- [ ] Toasts: integrar `toast.js` com `.rm-toast-stack`
- [ ] Onboarding tooltips (primeiro acesso)
- [ ] Page transitions entre navegação (opcional View Transitions API)

---

## Fase 6 — Mobile

- [x] Sidebar overlay blur
- [ ] Tabelas → cards em `< 576px` onde aplicável
- [ ] Touch targets mínimo 44px audit
- [ ] Testar iOS Safari scroll + `mobile-scroll-fix.css`

---

## Fase 7 — Qualidade

- [ ] Auditoria contraste WCAG AA (ferramenta automática)
- [ ] Teste keyboard-only em sidebar e modais
- [ ] Lighthouse performance (animaciones)
- [ ] Remover CSS duplicado morto em `styles.css` (refactor seguro)
- [ ] Considerar build pipeline (opcional: postcss nest)

---

## Fase 8 — Assets

- [ ] Sincronizar `static/img/` com `logos-rmsys/` (letreiro, favicon)
- [ ] SVG wordmark para topbar (performance)
- [ ] `manifest.json` theme_color dark `#070d18`

---

## Templates — inventário (95 arquivos)

Prioridade alta (uso diário):

- [x] `templates/base.html`
- [ ] `core/templates/core/company_dashboard.html`
- [x] `core/templates/core/rm_dashboard.html`
- [ ] `core/templates/core/company_hub.html`
- [ ] `templates/company/users/list.html`
- [ ] `templates/rm/users/list.html`
- [ ] `templates/company/tickets/list.html`
- [ ] `templates/rm/tickets/list.html`
- [ ] `templates/login.html` / `templates/company/login.html`

Prioridade média: maps, reports, OLT, alerts, MFA, legal, docs.

Prioridade baixa: emails HTML, password reset.

---

## Regras de ouro (não quebrar)

1. Não renomear `id` usados em JS (`sidebar`, `sidebarToggle`, `theme-toggle`, `main-content`)
2. Não remover classes `active` da sidebar (lógica Django)
3. Não alterar `name` de inputs de formulário
4. Manter CSP nonce em scripts inline novos
5. Testar dark + light após cada página tocada

---

## Estimativa

| Fase | Esforço relativo |
|------|------------------|
| 0–1 | Concluída |
| 2–3 | 3–5 dias |
| 4–5 | 4–6 dias |
| 6–8 | 2–3 dias |

**Total restante:** ~2 semanas para cobertura 100% das telas com polish uniforme.
