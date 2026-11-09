# READINESS VISUAL / UX — RM Systems

> **Data:** 25/05/2026  
> **Modo:** Fase 1 — auditoria somente leitura (nenhuma alteração de código)  
> **Objetivo:** diagnóstico completo antes do overhaul visual premium  
> **Escopo:** SaaS multi-tenant Django SSR — plataforma ISP (Verificador, Alertas, OLT, RM Admin)

---

## 1. Resumo executivo

O RM Systems já possui **fundação visual parcial** (tokens DS v2 em `static/css/ds/`, dark mode, hub modular, dashboards RM/company, verificador FTTH standalone). Porém a experiência ainda é **fragmentada**: múltiplos shells, CSS empilhado (15+ folhas no `base.html`), versões duplicadas de vendors e páginas “cruas” convivendo com páginas premium.

| Dimensão | Score (0–10) | Leitura |
|----------|:------------:|---------|
| **UX operacional** | **6.2** | Fluxos críticos funcionam; navegação duplicada; gaps mobile/PWA |
| **Motion design** | **5.8** | Base em `rm-ui.js` + `ds/animations.css`; inconsistente entre módulos |
| **Impacto comercial** | **5.5** | Marca RM presente; ainda não transmite “produto enterprise caro” de forma uniforme |
| **Enterprise / ISP** | **6.5** | Multi-tenant, quotas, MFA, auditoria — visual não acompanha maturidade técnica |
| **Consistência visual** | **4.8** | Maior gap do sistema |
| **Performance visual** | **5.5** | Bundle CSS pesado; motion GPU-friendly onde existe; LCP penalizado pelo stack |
| **Acessibilidade visual** | **5.0** | Zoom bloqueado; reduced motion parcial; contraste OK no shell principal |

**Veredito:** pronto para **Fase 2 (design system unificado + shells v2)** com rollback simples via feature flag de template/CSS. **Não** está pronto para “big bang” visual em produção sem fases.

**Referências obrigatórias (direção, não cópia):**

| Referência | O que extrair | O que NÃO copiar |
|------------|---------------|------------------|
| [Mimo (Xiaomi)](https://mimo.xiaomi.com/) | Motion suave, cards profundos, hierarquia limpa, sensação “produto vivo” | Landing consumer; hero marketing |
| [Ret Tecnologia](https://www.rettecnologia.org/) | Credibilidade telecom, contraste operacional, foco B2B | Site institucional estático |

**North star:** *“Sistema operacional de ISP moderno, premium, rápido e vivo”* — operacional primeiro, bonito depois, nunca landing genérica.

---

## 2. Inventário de shells e layouts

### 2.1 Shells principais

| Shell | Arquivo | Uso | Score visual |
|-------|---------|-----|:------------:|
| **App principal** | `templates/base.html` | ~62 páginas autenticadas | 7/10 |
| **Minimal** | `templates/base_minimal.html` | Senha obrigatória, fluxos sensíveis | 6/10 |
| **Docs** | `templates/docs_base.html` | Legal, FAQ, ajuda | 6/10 |
| **OLT wrapper** | `templates/olt_ops/base_olt.html` | Módulo OLT | 7/10 |
| **FTTH standalone** | `ftth_viewer/templates/ftth_viewer/index.html` | Mapa full-screen | 7.5/10 (pós-ajustes recentes) |
| **Auth standalone** | `templates/login.html`, `company/login.html` | Login RM / tenant | 7/10 |
| **Erro genérico** | `templates/errors/generic.html` | Fora do DS (gradiente roxo) | 3/10 |
| **E-mail** | `templates/core/email/base_transactional.html` | Transacional | 7/10 |

### 2.2 Hierarquia de herança (simplificada)

```
base.html
├── docs_base.html → legal/*, docs/*
├── base_olt.html → olt_ops/*
├── core/templates/core/* (hub, dashboards, upload, rm_*)
├── templates/rm/*, company/*, alerts/*, core/mfa_*
└── templates/errors/4xx|5xx.html

Standalone: login*, password_reset*, ftth_viewer/index.html, account_activate.html
```

### 2.3 Layout regions (shell principal)

| Região | Implementação | Observações |
|--------|---------------|-------------|
| Topbar | `.topbar` em `base-layout.css` | Brand, toggler, nav links, user menu |
| Sidebar | `#sidebar` + `saas_sidebar_modules.html` | Só admin RM / company_admin |
| Main | `.main-container` + mesh background | Breadcrumbs via `{% rm_breadcrumbs %}` |
| Footer | `.footer__links` | Legal/LGPD |
| Overlays | `#global-loading-overlay`, toasts | FTTH desliga global loading |

---

## 3. Inventário de páginas críticas

### 3.1 Matriz prioridade × maturidade visual

| Página | Template | Tráfego esperado | Maturidade | Prioridade overhaul |
|--------|----------|------------------|:----------:|:-------------------:|
| **Hub módulos** | `core/company_hub.html` | Alto | Média-alta | P1 |
| **Login RM/Company** | `login.html`, `company/login.html` | Alto | Média-alta | P1 |
| **Dashboard RM** | `core/rm_dashboard.html` | Alto | Média | P1 |
| **Dashboard Company** | `core/company_dashboard.html` | Alto | Média | P1 |
| **Verificador FTTH** | `ftth_viewer/index.html` | Alto | Alta (isolado) | P1 |
| **Upload mapas** | `core/upload_page.html` | Médio | Média | P2 |
| **Alertas WhatsApp** | `alerts/settings.html` | Médio | Baixa (inline CSS) | P2 |
| **OLT home/live** | `olt_ops/home.html`, `job_live.html` | Médio | Média | P2 |
| **Users RM/Company** | `rm/users/*`, `company/users/*` | Médio | Média-baixa | P2 |
| **Tickets** | `*/tickets/*` | Médio | Média | P3 |
| **Relatórios** | `rm/reports.html`, `company/reports.html` | Baixo-médio | Média | P3 |
| **MFA** | `core/mfa_*.html` | Baixo (crítico segurança) | Baixa | P2 |
| **Legal/Docs** | `legal/*`, `docs/*` | Baixo | Média | P4 |
| **Dashboard legado** | `templates/dashboard.html` | ? (legado) | Baixa | Deprecar |

### 3.2 Páginas mais fracas (top 10)

1. `templates/errors/generic.html` — visual alienígena ao RM  
2. `templates/core/mfa_verify.html`, `mfa_setup.html` — estilos inline, sem DS  
3. `templates/alerts/settings.html` — QR box `#fff` fixo, quebra dark  
4. `templates/dashboard.html` — legado, nav duplicada  
5. `templates/core/account_activate.html` — Bootstrap 5.1 isolado  
6. `templates/core/consent_required.html` — layout básico  
7. `templates/core/my_data_portal.html` — inline styles extensos  
8. `templates/legal/lgpd.html` — inline styles, fora do DS  
9. `templates/rm/users/list.html` — onclick legado, densidade alta  
10. `templates/company/users/form.html` — CSS inline local  

### 3.3 Páginas mais fortes (referência interna)

1. `core/company_hub.html` + `platform.css` — module cards, hero  
2. `core/rm_dashboard.html` + `rm-dashboard.css` — KPI grid  
3. `ftth_viewer/index.html` — shell dedicado, motion recente  
4. `templates/login.html` + `login.css` — auth premium parcial  
5. `templates/olt_ops/home.html` — usa `ds-steps`, `ds-alert`  

---

## 4. Inventário CSS / JS

### 4.1 Stack CSS carregado em `base.html` (15+ arquivos)

| Camada | Arquivos | Papel |
|--------|----------|-------|
| Tokens marca | `theme_colors.css`, `theme_rm.css` | Cores RM, aliases `--rm-*` |
| Legado | `styles.css` (~1900 linhas) | Estilos históricos amplos |
| Plataforma | `platform.css`, `global.css` | Hub, layout app |
| DS v1 | `design-system.css` | `.saas-page`, `.ds-*` |
| DS v2 | `ds/variables.css`, `theme.css`, `components.css`, `layout.css`, `utilities.css` | Tokens modernos |
| Layout | `base-layout.css`, `app-responsive.css` | Topbar, sidebar, breakpoints |
| Motion/loading | `ds/animations.css`, `global-loading.css`, `loading-states.css` | Animações, overlay |
| Bootstrap | `bootstrap-theme.css` + vendor 5.3.3 | Overrides + grid |
| Feature (por página) | `rm-dashboard.css`, `rm-form.css`, etc. | Escopados via `extra_head` |

**Problema central:** coexistência **DS v1 + DS v2 + legado** sem fronteira clara.

### 4.2 JavaScript UX

| Arquivo | Responsabilidade | Maturidade |
|---------|------------------|:----------:|
| `rm-ui.js` | Command palette, sidebar collapse, partículas, theme transition | Alta |
| `dark-mode.js` | Toggle, localStorage `rm-theme` | Alta |
| `global-loading.js` | Overlay global | Alta |
| `defer-css.js` | CSS defer CSP-safe | Média |
| `sidebar-nav.js` | Mobile sidebar | Média |
| `toast.js` | Notificações | Média |
| `skeleton.js`, `loading-states.js` | Loading UX | Média-baixa (adoção parcial) |
| `ux-forms.js` | Forms | Média-baixa |
| `quota-progress.js` | Barras quota | Alta |
| `ftth_viewer/js/app.js` | Mapa FTTH | Alta (isolado) |

### 4.3 Vendors duplicados (risco consistência)

| Lib | Versões no repo | Páginas |
|-----|-----------------|---------|
| Bootstrap | 5.1.3, 5.3.3 | 5.1: account_activate; 5.3: app |
| Chart.js | 4.4.1, 4.4.4 | RM vs company reports |
| Font Awesome | 6.0.0, 6.5.2, 6.0 em base | Mix por include |

---

## 5. Componentes repetidos

| Componente | Localização | Estado |
|------------|-------------|--------|
| Topbar | `base.html`, `base-layout.css` | Premium parcial |
| Sidebar | `base.html`, `saas_sidebar_modules.html` | Collapse + glow; sem tooltips |
| User menu | `topbar_user_menu.html` | OK |
| Breadcrumbs | `ui_tags.py` → `rm_breadcrumbs` | Funcional, visual básico |
| Hub module cards | `company_hub.html`, `platform.css` | Bom |
| SaaS panel/card | `design-system.css`, `ds/components.css` | Duplicado |
| KPI stats | `rm-dashboard.css` | Hover OK; sem counter anim |
| Quota panel | `quota_usage.html`, `ds/components.css` | Bom |
| Empty state | `rm_empty_state.html` | Adoção parcial |
| Tables | `.rm-table-wrap` | Parcial |
| Forms | `.rm-field`, `rm-form.css` | Parcial |
| Toasts | `toast.js` | OK |
| Messages Django | `.messages` vs Bootstrap `.alert` | **Duplicado** |

---

## 6. Dark mode

| Aspecto | Status |
|---------|--------|
| Mecanismo | `data-theme` + `dark-mode.js` + FOUC script em `base.html` |
| Cobertura shell principal | ~85% |
| FTTH viewer | Próprio; meta `#121212` vs base `#070d18` |
| Alertas QR | **Quebrado** (fundo branco fixo) |
| MFA / consent | **Sem DS** |
| `theme-color` meta | 3 valores diferentes (#003366, #070d18, #121212) |
| Manifest | `#1D4ED8` (quarto valor) |

---

## 7. PWA / Electron / Mobile

| Item | Status |
|------|--------|
| `manifest.json` | Presente; shortcuts/screenshots vazios |
| Service Worker | Registra **apenas localhost** (`pwa.js`) |
| `browserconfig.xml` | Referenciado no head, **ausente** |
| Electron | **Não implementado** no repo |
| Mobile | `app-responsive.css`, `mobile-scroll-fix.css`, FTTH `mobile.css` |
| Touch | Botões 44px em várias áreas OLT/mobile |

---

## 8. Módulos ausentes no escopo atual

| Módulo mencionado no brief | Status no codebase |
|----------------------------|-------------------|
| **PDV / POS** | **Não existe** — planejar como módulo greenfield (Fase 4 do brief) |
| **Billing UI** | Parcial (quotas, Asaas backend); sem UI billing premium |
| **base_pdv_v2.html** | A criar na Fase 4 |

---

## 9. Gargalos visuais e inconsistências

### 9.1 Críticos (bloqueiam percepção premium)

1. **Fragmentação de shells** — 4+ experiências visuais distintas  
2. **CSS stack excessivo** — LCP, cache, manutenção  
3. **DS duplo** — `design-system.css` vs `css/ds/*`  
4. **Páginas admin “cruas”** — MFA, alertas, legado  
5. **Dark mode com buracos** — contraste quebrado em QR/inline  

### 9.2 Moderados

6. Navegação tripla (topbar + sidebar + command palette)  
7. Sidebar ausente para `company_user` comum  
8. Dashboard legado coexistindo  
9. Chart.js / FA / Bootstrap version drift  
10. Console suprimido em produção (`base.html`) — dificulta suporte UX  

### 9.3 Menores

11. `maximum-scale=1` no viewport — a11y  
12. Partículas em `rm-ui.js` — custo GPU em VPS fraca  
13. Fontes Google externas — CSP/latência  
14. Animações FTTH não compartilhadas com shell principal  

---

## 10. Motion design — estado atual

### 10.1 O que já existe

| Tipo | Onde | Qualidade |
|------|------|-----------|
| Page enter | `.ds-content-enter`, `rm-fade-in-up` | Boa |
| Theme transition | `rm-theme-transition` | Boa |
| Loading overlay | `global-loading.css`, FTTH loading | Boa |
| Skeleton/shimmer | `design-system.css`, `skeleton.js` | Adoção baixa |
| Hover lift | `.rm-lift`, KPI cards | Média |
| Command palette | `rm-ui.js` | Boa (desligada com reduced motion) |
| Sidebar collapse | `rm-ui.js` | Média |
| Chart animation | Chart.js default | Não tematizado dark |
| FTTH map popups | `ftth_viewer/style.css` | Boa (recente) |

### 10.2 O que falta (motion system unificado)

- Tokens motion centralizados em `static/css/motion/` (proposta Fase 2)  
- `prefers-reduced-motion` global consistente  
- Route transition leve (fade main content) sem SPA  
- Counter animation KPIs (CSS/JS vanilla)  
- Stagger lists (`.rm-stagger` existe, adoção ~30%)  
- Feedback operacional padronizado (success/error pulse)  
- Skeleton em **todas** listagens AJAX  

### 10.3 Score motion por área

| Área | Score |
|------|:-----:|
| Shell global | 6.5 |
| Dashboard | 5.5 |
| Auth | 6.0 |
| FTTH | 8.0 |
| Listagens | 4.5 |
| Forms | 4.0 |
| Alertas/OLT | 5.0 |

---

## 11. Proposta de design system (Fase 2)

### 11.1 Estrutura de pastas alvo

```
static/css/
  design-system/
    tokens.css          ← merge theme_colors + ds/variables
    typography.css
    elevation.css
    gradients.css
    glass.css
    themes/
      light.css
      dark.css
    motion/
      transitions.css
      animations.css
      reduced-motion.css
    components/
      buttons.css
      cards.css
      forms.css
      tables.css
      badges.css
      modals.css
      toasts.css
      sidebar.css
      topbar.css
    layouts/
      shell-app.css
      shell-auth.css
      shell-dashboard.css
      shell-docs.css
    pages/
      hub.css
      dashboard.css
      ftth.css
      alerts.css
      olt.css
```

### 11.2 Princípios

1. **Um token, um lugar** — deprecar aliases conflitantes gradualmente  
2. **Componentes composáveis** — `.ds-btn`, `.ds-card`, `.ds-panel` únicos  
3. **Motion via CSS first** — JS só para orchestration (contadores, route fade)  
4. **Glass leve** — blur ≤ 16px; fallback sólido em `prefers-reduced-transparency`  
5. **ISP operacional** — densidade informação > whitespace de marketing  

### 11.3 Shells v2 (Fase 2–3)

| Template proposto | Baseado em | Feature flag sugerida |
|-------------------|------------|------------------------|
| `base_app_v2.html` | `base.html` | `UI_V2=1` env ou cookie |
| `base_auth_v2.html` | `login.html` | idem |
| `base_dashboard_v2.html` | extends app_v2 | idem |
| `base_pdv_v2.html` | greenfield | módulo futuro |

Rollback: manter `base.html` intacto; páginas opt-in via `{% extends "base_app_v2.html" %}`.

---

## 12. Direção visual alinhada às referências

### 12.1 Linguagem visual RM v2

| Elemento | Direção |
|----------|---------|
| Cor base dark | `#070d18` (manter) + superfícies `#121a2e`, `#1a2332` |
| Accent | Cyan `#00d2ff` + deep blue `#003366` (marca) |
| Tipografia | Plus Jakarta Sans (display) + system UI (dados) |
| Radius | 12px cards, 8px inputs, pill badges |
| Elevação | 3 níveis + glow cyan sutil em active/focus |
| Glass | Topbar blur 12px; modais blur 16px |
| Densidade | Dashboard compacto; PDV futuro touch-large |

### 12.2 Sensação alvo (adjacentes)

Linear (sidebar pill) · Stripe (dashboard clarity) · Vercel (dark premium) · Raycast (command palette) · Notion (hierarchy) · Mimo (motion fluido)

---

## 13. Plano de execução por fases

### Fase 1 — Auditoria ✅ (este documento)

- [x] Inventário shells, templates, CSS, JS  
- [x] Scores UX / motion / comercial / enterprise  
- [x] Inconsistências e páginas críticas  
- [x] Proposta DS e shells v2  
- **Entregável:** `docs/READINESS_VISUAL_UX.md`  
- **Código alterado:** nenhum  

### Fase 2 — Design system + motion + shells

| Entrega | Detalhe |
|---------|---------|
| `design-system/tokens.css` | Unificação tokens |
| `motion/*.css` | Sistema motion reutilizável |
| `base_app_v2.html` | Shell premium opt-in |
| Relatório | `docs/UI_PHASE2_REPORT.md` |
| Rollback | Flag UI_V2 off → `base.html` |

**Impacto performance:** reduzir 15→8 CSS no shell (meta LCP -15%)  
**Risco:** regressão dark mode — mitigar com checklist por página  

### Fase 3 — Dashboard + auth + sidebar + topbar

| Área | Ações |
|------|-------|
| Dashboard RM/Company | KPI animate, chart theme, skeleton |
| Auth | `base_auth_v2`, MFA com DS |
| Sidebar | Pill active, tooltips, tenant badge |
| Topbar | Blur, status dot, notificações UI |

**Entregável:** `docs/UI_PHASE3_REPORT.md` + screenshots antes/depois  

### Fase 4 — PDV premium (greenfield)

> **Pré-requisito:** definir escopo backend PDV (não existe hoje)

- `base_pdv_v2.html` touch-first  
- Numpad, F-keys, feedback bip, estados caixa  
- **Entregável:** `docs/UI_PDV_SPEC.md`  

### Fase 5 — Mapas, billing, auxiliares

- FTTH tokens unificados com shell  
- Alertas sem inline CSS  
- Billing widgets (quando UI existir)  
- Legal/docs paridade DS  

### Fase 6 — Polish

- Lighthouse ≥ 85 performance / ≥ 95 a11y (shell principal)  
- CLS < 0.1, LCP < 2.5s (VPS referência)  
- `prefers-reduced-motion` audit  
- Remover `styles.css` legado (ou namespace)  

---

## 14. Performance e restrições

| Meta | Abordagem |
|------|-----------|
| Sem bundle JS gigante | CSS-first; GSAP só se counter complexo |
| GPU motion | `transform`/`opacity` only; `will-change` sparingly |
| VPS modesta | Desligar partículas por default em prod |
| Lighthouse | Consolidar CSS; defer não-crítico; preload tokens |
| Electron-ready | Sem dependência window APIs exóticas |
| PWA | Decidir: SW prod ou remover manifest do head |
| CSP | Manter nonce; zero inline novo |

---

## 15. Riscos e rollback

| Risco | Probabilidade | Mitigação |
|-------|:-------------:|-----------|
| Regressão dark | Alta | Checklist 20 páginas; screenshot diff manual |
| LCP piora | Média | Bundle budget; critical CSS inline tokens |
| Electron quebra | Baixa | Testar file:// + PWA paths |
| Adoção parcial DS | Alta | Lint template: proibir inline style |
| Scope creep PDV | Alta | PDV fora do repo atual — spec separada |

**Rollback simples:** variável `UI_V2=false` + extends revert em templates tocados.

---

## 16. Checklist de prontidão para iniciar Fase 2

| Item | OK? |
|------|:---:|
| Inventário visual completo | ✅ |
| Scores baseline documentados | ✅ |
| Proposta DS estruturada | ✅ |
| Shells v2 especificados | ✅ |
| Feature flag strategy | ✅ |
| PDV marcado como greenfield | ✅ |
| FRONTEND_REFACTOR_TODO.md alinhado | ⚠️ atualizar refs a este doc |
| Aprovação stakeholders direção visual | ⬜ pendente |

---

## 17. Documentos relacionados

| Documento | Relação |
|-----------|---------|
| `docs/FRONTEND_REFACTOR_TODO.md` | Checklist implementação (Fases 0–4 parciais) |
| `docs/READINESS_TECNICO_OPERACIONAL.md` | Readiness backend/ops |
| `static/css/ds/variables.css` | Tokens DS v2 existentes |
| `docs/DESIGN_SYSTEM.md` | Doc DS anterior (revisar na Fase 2) |

---

## 18. Conclusão

O RM Systems está na **zona de transição**: já investiu em DS v2, dark mode e módulos premium pontuais (hub, FTTH), mas a **consistência visual ainda não sustenta a promessa comercial enterprise**. A Fase 2 deve **unificar tokens e shells** antes de “embelezar” página por página — caso contrário, o overhaul vira patchwork.

**Próximo passo recomendado:** aprovar direção visual deste documento → iniciar Fase 2 com `base_app_v2.html` + consolidação CSS (sem remover legado até Fase 6).

---

*Gerado em modo auditoria — Fase 1. Nenhum arquivo de aplicação foi modificado.*
