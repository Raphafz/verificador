# UI Phase 2 Report — Overhaul Visual Premium RM Systems

> **Data:** 25/05/2026  
> **Escopo:** Fase 2A + 2B (parcial) — Design System, Motion, Shell V2, Dashboards, Auth  
> **Status:** Implementado (opt-in) — legado intacto

---

## 1. Resumo executivo

Entregue a **fundação visual unificada** do RM Systems v2:

- Design system modular em `static/css/design-system/`
- Motion system em CSS + `static/js/rm-motion.js`
- Shell operacional `base_app_v2.html` (sidebar persistente desktop, blur topbar)
- Shell auth `base_auth_v2.html`
- Feature flag `UI_V2` + preview `?v2=1`
- Dashboards RM/Company e Hub migrados para shell dinâmico
- Login e MFA com templates v2 quando flag ativa

**Rollback:** `UI_V2=false` ou `?v2=0` — páginas voltam a `base.html` / templates legados.

---

## 2. Subfases entregues

### Fase 2A ✅

| Item | Arquivo(s) |
|------|------------|
| Tokens unificados | `design-system/tokens.css` |
| Tipografia, elevação, gradientes, glass | `typography.css`, `elevation.css`, `gradients.css`, `glass.css` |
| Motion system | `motion/transitions.css`, `motion/animations.css`, `motion/reduced-motion.css` |
| Temas light/dark | `themes/light.css`, `themes/dark.css` |
| Bundle entry | `design-system/bundle.css` |
| Shell app v2 | `templates/base_app_v2.html` |
| Sidebar premium | `components/sidebar.css`, `includes/sidebar_v2_nav.html` |
| Topbar premium | `components/topbar.css` |
| Motion JS | `static/js/rm-motion.js` |
| Feature flag | `UI_V2`, `core/ui_helpers.py`, `core/middleware_ui_v2.py` |

### Fase 2B ✅ (parcial)

| Item | Status |
|------|--------|
| Dashboard RM | Migrado (`ui_shell`, KPI counters, stagger) |
| Dashboard Company | Migrado |
| Hub módulos | Migrado (`ui_shell`) |
| Login RM/Company | `auth/login_v2.html` via `ui_template()` |
| MFA verify | `auth/mfa_verify_v2.html` |
| Forms/tables DS | CSS pronto; adoção gradual pendente |
| Alertas/OLT inline CSS | CSS pages prontos; templates Fase 2C |

### Fase 2C / 2D — Pendente

- Alertas settings (remover inline)
- OLT pages full migration
- Legal/docs paridade
- Consolidação CSS legado / Lighthouse audit

---

## 3. Como ativar

### Opção A — Global (`.env`)

```env
UI_V2=true
```

### Opção B — Preview por cookie

```
https://seu-dominio/rm/admin/?v2=1
```

Cookie `rm-ui-v2=1` persiste 30 dias. Desativar: `?v2=0`.

### Opção C — Por template (já wired)

Templates usam `{% extends ui_shell %}` — alternam automaticamente.

---

## 4. Páginas migradas

| Página | Template | Shell v2 quando UI_V2 |
|--------|----------|:---------------------:|
| Dashboard RM | `core/rm_dashboard.html` | ✅ |
| Dashboard Company | `core/company_dashboard.html` | ✅ |
| Hub | `core/company_hub.html` | ✅ |
| Login RM | `auth/login_v2.html` | ✅ |
| Login Company | `auth/login_v2.html` | ✅ |
| MFA Verify | `auth/mfa_verify_v2.html` | ✅ |
| Demais páginas | `base.html` | ❌ (legado) |

---

## 5. Antes / Depois (descrição)

| Área | Antes | Depois (v2) |
|------|-------|---------------|
| CSS stack shell | 15+ arquivos | ~5 críticos + bundle |
| Sidebar | Overlay mobile-only feel | Persistente desktop + pill active + collapse |
| Topbar | Gradiente sólido | Glass blur + status operacional + tenant badge |
| KPIs | Estáticos | Counter animation (`data-rm-counter`) |
| Motion | Fragmentado | Sistema unificado + `prefers-reduced-motion` |
| Auth MFA | Inline styles, base genérico | Card premium, DS forms |
| Login | Split marketing layout | Card centrado enterprise |

---

## 6. Impacto performance

| Métrica | Estimativa | Notas |
|---------|------------|-------|
| CSS shell v2 | **−40% requests** vs base.html | 1 bundle vs 15 links |
| JS adicional | **+3KB** gzip (`rm-motion.js`) | Vanilla, sem libs |
| GPU motion | Baixo | `transform`/`opacity` only |
| LCP | Neutro a + | Menos CSS blocking; fontes iguais |
| CLS | Melhor | Topbar height tokenizado 64px |

**Risco:** `@import` chain no bundle — em prod considerar concatenação futura (Fase 2D).

---

## 7. Impacto Electron / PWA

| Plataforma | Impacto |
|------------|---------|
| Electron futuro | ✅ Sem APIs exóticas; CSS vars + vanilla JS |
| PWA | ✅ Neutro; manifest inalterado |
| Mobile | ✅ Sidebar overlay preservado <992px |
| CSP | ✅ Sem inline novo (exc. critical loading já existente) |

---

## 8. Riscos

| Risco | Severidade | Mitigação |
|-------|:----------:|-----------|
| Conflito platform.css vs v2 | Média | Overrides `.rm-ui-v2` alta especificidade |
| Sidebar desktop vs overlay legado | Baixa | `sidebar-nav.js` detecta v2+desktop |
| Hub sem platform.css | Resolvido | platform.css incluído em base_app_v2 |
| Chart.js tema dark | Baixa | `rm-motion.js` initChartTheme |
| Login company perde hero marketing | Esperado | v2 = auth enterprise, não landing |

---

## 9. Rollback

1. `UI_V2=false` no `.env` → restart app  
2. Ou visitar qualquer URL com `?v2=0`  
3. Templates legados (`base.html`, `login.html`) **não foram removidos**  
4. Remover `{% extends ui_shell %}` reverte página individual  

---

## 10. Estrutura de arquivos criados

```
static/css/design-system/
  tokens.css, typography.css, elevation.css, gradients.css, glass.css
  animations.css, bundle.css
  motion/transitions.css, animations.css, reduced-motion.css
  themes/light.css, dark.css
  components/*.css (10 arquivos)
  layouts/shell-app.css, shell-auth.css, shell-dashboard.css
  pages/dashboard.css, hub.css, ftth.css, alerts.css, olt.css

static/js/rm-motion.js

templates/base_app_v2.html
templates/base_auth_v2.html
templates/auth/login_v2.html
templates/auth/mfa_verify_v2.html
templates/includes/ui_v2_styles.html
templates/includes/sidebar_v2_nav.html

core/ui_helpers.py
core/middleware_ui_v2.py
```

---

## 11. Próximos passos (Fase 2C–2D)

1. Migrar `alerts/settings.html` — remover inline, classe `alerts-console`
2. OLT templates → `olt-console`
3. Forms principais → `.ds-field`
4. Tabelas restantes → `.ds-table-wrap`
5. FTTH: importar `pages/ftth.css` bridge no viewer
6. Lighthouse audit + concat bundle CSS
7. Screenshots formais before/after (manual QA)

---

## 12. QA manual sugerido

- [ ] `UI_V2=true` → dashboard RM carrega sidebar persistente (desktop)
- [ ] KPIs animam contadores ao load
- [ ] `Ctrl+K` abre command palette
- [ ] Collapse sidebar (desktop) + tooltips
- [ ] Mobile: hamburger abre overlay
- [ ] Dark mode sem regressão
- [ ] Login v2 + MFA v2
- [ ] `?v2=0` restaura legado
- [ ] Hub module cards hover premium

---

*Relatório gerado na Fase 2 — rollout gradual, zero big-bang.*
