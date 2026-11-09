# RM Systems — Design System v2

Documentação dos tokens e padrões visuais. Implementação em `static/css/ds/`.

---

## Paleta obrigatória

| Nome | Token | Hex | Uso |
|------|-------|-----|-----|
| Azul profundo | `--rm-brand-deep` | `#003366` | Marca, primário light, gradientes |
| Ciano elétrico | `--rm-brand-cyan` | `#00D2FF` | Accent, focus, dark primary, glow |
| Antracite | `--rm-brand-anthracite` | `#2C3E50` | Texto light |
| Branco neve | `--rm-brand-snow` | `#F8F9FA` | Fundos secundários light |

### Dark mode

| Superfície | Hex |
|------------|-----|
| Background primary | `#070d18` |
| Background secondary | `#0c1526` |
| Background tertiary | `#132238` |
| Card | `rgba(12, 21, 38, 0.92)` |

---

## Tipografia

- **Display:** Plus Jakarta Sans (`--rm-font-display`)
- **Mono:** system ui-monospace (`--rm-font-mono`)

| Token | Tamanho |
|-------|---------|
| `--rm-text-xs` | 0.75rem |
| `--rm-text-sm` | 0.8125rem |
| `--rm-text-base` | 1rem |
| `--rm-text-lg` | 1.125rem |
| `--rm-text-xl` | 1.25rem |
| `--rm-text-2xl` | 1.5rem |
| `--rm-text-3xl` | 1.875rem |
| `--rm-text-4xl` | 2.25rem |

**Tracking:** `--rm-tracking-tight` (-0.03em) em títulos.

---

## Espaçamento

Escala 4px base: `--rm-space-1` (4px) … `--rm-space-16` (64px).

---

## Border radius

| Token | Valor |
|-------|-------|
| `--rm-radius-xs` | 6px |
| `--rm-radius-sm` | 8px |
| `--rm-radius-md` | 12px |
| `--rm-radius-lg` | 16px |
| `--rm-radius-xl` | 20px |
| `--rm-radius-2xl` | 24px |
| `--rm-radius-pill` | 9999px |

---

## Sombras e elevação

| Token | Uso |
|-------|-----|
| `--rm-elevation-1` | Cards em repouso |
| `--rm-elevation-2` | Hover leve |
| `--rm-elevation-3` | Modais, dropdowns |
| `--rm-elevation-glow` | Hover premium / dark |
| `--rm-glow-cyan` | Focus / active |

---

## Motion

| Token | Valor |
|-------|-------|
| `--rm-ease-out` | cubic-bezier(0.16, 1, 0.3, 1) |
| `--rm-ease-spring` | cubic-bezier(0.34, 1.56, 0.64, 1) |
| `--rm-duration-fast` | 120ms |
| `--rm-duration-normal` | 220ms |
| `--rm-duration-slow` | 380ms |
| `--rm-duration-page` | 480ms |

**Regra:** preferir `transform` + `opacity`. Respeitar `prefers-reduced-motion`.

---

## Glass

```css
--rm-glass-bg: rgba(255, 255, 255, 0.72); /* light */
--rm-glass-blur: 16px;
--rm-glass-border: rgba(255, 255, 255, 0.35);
```

Classe: `.rm-glass-card`

---

## Z-index

| Token | Valor |
|-------|-------|
| `--rm-z-topbar` | 1100 |
| `--rm-z-sidebar` | 1050 |
| `--rm-z-overlay` | 1040 |
| `--rm-z-modal` | 1200 |
| `--rm-z-toast` | 1300 |
| `--rm-z-command` | 1400 |

---

## Componentes

### KPI

```html
<article class="rm-kpi rm-lift">
  <div class="rm-kpi__icon"><i class="fas fa-building"></i></div>
  <div>
    <p class="rm-kpi__value">42</p>
    <p class="rm-kpi__label">Empresas</p>
  </div>
</article>
```

Grid: `.rm-kpi-grid`

### Card

- `.ds-card` / `.saas-panel` (legado design-system.css)
- `.rm-glass-card` — glassmorphism
- `.rm-lift` — hover elevation

### Formulário

```html
<div class="rm-field">
  <label class="form-label" for="id_email">E-mail</label>
  <input class="form-control" id="id_email" type="email">
</div>
```

Floating (opcional): `.rm-field--floating`

### Tabela

Envolver `.table` em:

```html
<div class="rm-table-wrap">
  <table class="table table-striped">...</table>
</div>
```

### Badges

`.rm-badge .rm-badge--cyan|success|warning|danger`

### Empty state

```html
<div class="rm-empty">
  <div class="rm-empty__icon"><i class="fas fa-inbox"></i></div>
  <p class="rm-empty__title">Nada por aqui</p>
  <p>Descrição opcional.</p>
</div>
```

### Botão premium

`.btn.btn-primary.rm-btn-premium.rm-btn-ripple`

### Search

```html
<div class="rm-search">
  <i class="fas fa-search"></i>
  <input type="search" placeholder="Buscar…">
</div>
```

---

## Layout

| Classe | Descrição |
|--------|-----------|
| `.topbar` | Header fixo gradiente |
| `.sidebar` | Menu lateral overlay (mobile) |
| `.sidebar-collapsed` | Body class — sidebar estreita (desktop) |
| `.saas-page` | Container de página interna |
| `.ds-content-enter` | Animação entrada |
| `.rm-breadcrumb-bar` | Breadcrumbs |

---

## Tema (JavaScript)

- Chave: `localStorage['rm-theme']` → `'light' | 'dark'`
- Evento: `document.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }))`
- Atributo HTML: `data-theme="light|dark"`

---

## Command palette

- Atalho: **Ctrl+K** / **Cmd+K**
- Fechar: **Esc**
- Classe: `.rm-command-palette.is-open`

---

## Aliases legados (manter)

Todo código antigo pode continuar usando:

- `--rm-primary`, `--rm-card-bg`, `--rm-text-primary`
- `.saas-page`, `.module-card`, `.rm-dash__stat`

Novos desenvolvimentos devem preferir tokens `--rm-brand-*` e classes `rm-*`.

---

## Referências visuais

Linear · Stripe Dashboard · Vercel · Supabase · Notion · Raycast · Clerk · GitHub Modern UI

Mistura: minimalismo premium + motion sutil + glass leve + depth moderna.
