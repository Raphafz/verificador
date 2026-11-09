# UI Phase 2C Report — Alertas, OLT, Legal, Auth auxiliar

> **Data:** 25/05/2026  
> **Escopo:** Fase 2C — módulos operacionais + páginas auxiliares  
> **Pré-requisito:** Fase 2A/2B (`UI_V2` ou `?v2=1`)

---

## 1. Resumo

Migração visual dos módulos **Alertas**, **OLT**, **Legal/Docs** e fluxos **auth auxiliares** para o design system v2, removendo inline CSS crítico e alinhando dark mode.

| Área | Status |
|------|--------|
| Alertas WhatsApp | ✅ |
| OLT / ONU (7 templates) | ✅ |
| LGPD (legal) | ✅ |
| Docs base (shell dinâmico) | ✅ |
| MFA setup | ✅ |
| Consent LGPD | ✅ |
| Ativar conta | ✅ |

---

## 2. Alertas

### Antes
- `<style>` inline em `settings.html` (~15 regras)
- QR box `#fff` fixo — quebrava dark mode
- Toggles JS via `element.style`

### Depois
- `static/css/design-system/pages/alerts.css` (escopo `.alerts-console`)
- Template: `{% extends ui_shell %}`, classe `alerts-console`
- QR box usa `--ds-bg-muted` (dark-safe)
- JS usa classes `.is-visible`, `.is-dimmed`

### Rollback
Reverter `templates/alerts/settings.html` para `base.html` + bloco `<style>` original.

---

## 3. OLT

### Arquivos migrados
| Template | Mudança |
|----------|---------|
| `base_olt.html` | `extends ui_shell`, carrega `olt.css` |
| `home.html` | `olt-console` wrapper |
| `olt_list.html` | idem |
| `olt_form.html` | `olt-console--narrow` |
| `job_form.html` | idem |
| `vpn_settings.html` | `olt-console--medium` |
| `job_detail.html` | `olt-console` |
| `job_live.html` | `olt-console` + live styles |

### CSS
- `pages/olt.css` expandido: steps, cards, alerts, live log, badges, forms
- Legado: `design-system.css` ainda carregado quando `not ui_v2`

---

## 4. Legal / Docs

### LGPD
- **Antes:** `base.html` + ~140 linhas inline style
- **Depois:** `docs_base.html` + classes `docs-section`, `docs-list` (paridade com Termos/Privacidade)

### Docs shell
- `docs_base.html` → `{% extends ui_shell %}`
- `pages/legal.css` — polish v2 sidebar/hero/article

---

## 5. Auth auxiliar (UI_V2)

| Fluxo | Template v2 |
|-------|-------------|
| MFA setup | `auth/mfa_setup_v2.html` |
| Consent | `auth/consent_v2.html` |
| Ativar conta | `auth/account_activate_v2.html` |

Views atualizadas: `mfa_views.py`, `lgpd_views.py`, `activation_views.py` via `ui_template()`.

---

## 6. Páginas migradas (total acumulado Fase 2)

| Página | Fase |
|--------|------|
| Dashboard RM/Company, Hub | 2B |
| Login, MFA verify | 2B |
| Alertas settings | 2C |
| OLT (7 páginas) | 2C |
| LGPD | 2C |
| Docs (via docs_base) | 2C |
| MFA setup, Consent, Activate | 2C |

---

## 7. Impacto performance

| Item | Impacto |
|------|---------|
| `alerts.css` | +4KB (~1KB gzip), 1 request quando legado |
| `olt.css` | Incluído no bundle v2; +1 request legado OLT |
| LGPD | −inline CSS, +HTML semântico (melhor cache) |
| JS alertas | Neutro (classes vs style) |

---

## 8. Riscos

| Risco | Mitigação |
|-------|-----------|
| OLT legado sem `design-system.css` em v2 | `olt.css` autossuficiente para componentes principais |
| Alertas QR contraste light | Testado via tokens `--ds-bg-muted` |
| Activate v2 sem Bootstrap 5.1 isolado | Usa `base_auth_v2` + DS forms |

---

## 9. QA manual

- [ ] Alertas: QR visível em dark mode
- [ ] Alertas: worker banner + pills de status
- [ ] OLT home: steps + cards + forms
- [ ] OLT job live: progress bar + log monospace
- [ ] LGPD: layout docs sidebar + conteúdo
- [ ] MFA setup: QR + backup codes
- [ ] Consent: checkbox + links legais
- [ ] Activate: form senha premium

---

## 10. Próximo — Fase 2D

1. Concatenar/minificar `bundle.css` (remover chain `@import`)
2. Migrar listagens (users, tickets, maps) → `.ds-table-wrap`
3. FTTH token bridge no viewer
4. Remover duplicação `design-system.css` vs bundle
5. Lighthouse audit + métricas formais

---

*Fase 2C concluída — rollout gradual mantido.*
