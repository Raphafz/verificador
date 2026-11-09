# UI/UX Redesign Report — RM Systems

**Data:** 2026-05-25  
**Escopo:** Remodelação visual enterprise sem alteração de backend, rotas ou lógica Django.

---

## 1. Resumo executivo

Foi implementada uma **camada visual premium v2** sobre o frontend existente, preservando:

- Templates Django e blocos `{% block %}`
- IDs e classes usados por JavaScript (`#sidebar`, `#sidebarToggle`, `#theme-toggle`, etc.)
- Aliases CSS legados (`--rm-*`, `.saas-page`, `.rm-dash__*`)
- Bootstrap 5.3 e Font Awesome

A sensação alvo — *SaaS enterprise estilo Linear/Stripe/Vercel* — é alcançada via **design tokens**, **dark mode profundo**, **motion GPU-friendly** e **componentes reutilizáveis**.

---

## 2. Identidade visual (logos-rmsys)

| Elemento | Origem | Uso no sistema |
|----------|--------|----------------|
| Azul profundo `#003366` | Fundo do ícone / marca | Topbar, gradientes, botões primários |
| Ciano elétrico `#00D2FF` | Monograma RM + `< />` | Focus, glow, links, dark mode accent |
| Antracite `#2C3E50` | Tipografia light | Texto principal light |
| Branco neve `#F8F9FA` | Fundos claros | Cards, sidebar light |

Arquivos de referência: `logos-rmsys/icon.png`, `logo.png`, `letreiro*.png`.

---

## 3. Arquitetura CSS implementada

Nova pasta modular (carregada **após** `design-system.css`):

```
static/css/ds/
├── variables.css   — tokens: spacing, typo, z-index, motion, glass, glow
├── theme.css       — dark enterprise, mesh de fundo, scrollbar, theme transition
├── animations.css  — fade, stagger, skeleton, ripple, modal, reduced-motion
├── components.css  — KPI, forms, tables, badges, empty, search, command palette
├── layout.css      — topbar, sidebar, footer, messages
└── utilities.css   — helpers responsivos e visuais
```

**Estratégia incremental:** não remover CSS legado (`styles.css`, `platform.css`, `theme_colors.css`). A v2 **sobrescreve visualmente** com maior especificidade e tokens novos.

---

## 4. Mudanças por área

### 4.1 Design system

- Tokens centralizados em `variables.css`
- Compatibilidade total com `--rm-*` em `theme_colors.css`
- Documentação em `docs/DESIGN_SYSTEM.md`

### 4.2 Dark mode enterprise

- Fundo: `#070d18` / `#0c1526` (profundidade azul, não cinza lavado)
- Cards com borda ciano sutil e sombra profunda
- Glow em hover (KPI, sidebar active, theme toggle)
- Transição `rm-theme-transition` ao alternar tema
- `localStorage` key: `rm-theme` (inalterada)
- Detecção `prefers-color-scheme` mantida

### 4.3 Animações

- Entrada de página: `.ds-content-enter`
- Stagger: `.rm-stagger`
- Cards: `.rm-lift`, `.rm-glow-hover`, `.rm-border-animated`
- Botões: `.rm-btn-ripple`
- Skeleton: `.rm-skeleton`
- `prefers-reduced-motion`: animações desligadas

### 4.4 Layout (topbar / sidebar)

- Topbar com sombra inset + gradiente marca
- Sidebar: indicador lateral ativo, overlay blur no mobile
- **Desktop:** botão recolher sidebar (`sidebar-collapsed`, persistência `rm-sidebar-collapsed`)
- Theme toggle com hover glow e rotação do ícone

### 4.5 Dashboards

- `rm-dashboard.css`: hover com elevação e glow no dark
- Classes `.rm-kpi*` disponíveis para novos widgets
- Mesh de fundo via `theme.css` em `.main-container`

### 4.6 Formulários e tabelas

- `.rm-field` com focus ring ciano
- `.rm-table-wrap` com sticky header e hover de linha
- Badges `.rm-badge--*`

### 4.7 Experiência premium

- **Command palette:** `Ctrl+K` / `Cmd+K` (UI preparada; busca em roadmap)
- **Partículas sutis:** canvas em desktop (desligado em mobile e reduced-motion)
- **Scrollbar** customizada
- Templates atualizados: `base.html`, `base_minimal.html`, `login.html`

### 4.8 JavaScript

- `static/js/rm-ui.js` — motion, sidebar collapse, command palette, partículas
- `dark-mode.js` — transição de tema + meta `#070d18`

---

## 5. Performance

- Animações usam `transform` e `opacity` onde possível
- Partículas pausam em `document.hidden`
- Partículas desativadas em viewport &lt; 768px
- `will-change: transform` apenas em `.rm-lift`

---

## 6. Acessibilidade

- `:focus-visible` preservado em `theme_colors.css`
- Skip link mantido em `base.html`
- Command palette com `role="dialog"` e `aria-hidden`
- Sidebar: `aria-expanded` / `aria-controls` inalterados
- Fallback `prefers-reduced-motion`

---

## 7. O que não foi alterado (por design)

- Views Django, URLs, permissões
- Nomes de campos de formulário
- Estrutura HTML de tabelas e modais existentes
- `ftth_viewer` (CSS próprio; integração futura no TODO)

---

## 8. Próximos passos

Ver checklist completo em `docs/FRONTEND_REFACTOR_TODO.md`.

Prioridade sugerida:

1. Aplicar `.rm-table-wrap` nas listagens (users, tickets, maps)
2. User dropdown na topbar (markup apenas, sem backend)
3. Unificar `login.css` com tokens `--rm-*` (reduzir duplicação `--img-*`)
4. FTTH viewer — importar tokens ds/
5. Testes visuais em dispositivos reais (iOS Safari)

---

## 9. Arquivos modificados nesta entrega

| Arquivo | Tipo |
|---------|------|
| `static/css/ds/*.css` | Novo |
| `static/js/rm-ui.js` | Novo |
| `templates/base.html` | CSS + JS |
| `templates/base_minimal.html` | CSS |
| `templates/login.html` | CSS + anti-flash theme |
| `static/css/theme_colors.css` | Dark premium |
| `static/css/rm-dashboard.css` | Hover glow |
| `static/js/dark-mode.js` | Transição tema |
| `docs/DESIGN_SYSTEM.md` | Novo |
| `docs/FRONTEND_REFACTOR_TODO.md` | Novo |
