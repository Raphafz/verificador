# RM Systems — Frontend SPA

React + Vite + TypeScript + Tailwind v4 + componentes estilo shadcn/ui.

## Desenvolvimento

```bash
npm install
npm run dev
npm run build
```

Abre em `http://localhost:5173`. Requisições `/api/*` são proxy para Django `:8000`.

### Testar no celular (sem criar conta)

```powershell
# Recomendado: Cloudflare quick tunnel (grátis, sem cadastro)
winget install Cloudflare.cloudflared   # uma vez
.\scripts\dev-tunnel.ps1
```

Outras opções:

```powershell
.\scripts\dev-tunnel.ps1 -Provider local        # mesma Wi-Fi, IP local (zero túnel)
.\scripts\dev-tunnel.ps1 -Provider localtunnel  # npx localtunnel, sem conta
.\scripts\dev-tunnel.ps1 -Provider ngrok        # exige conta ngrok
```

Abra a URL HTTPS no celular (Wi‑Fi ou 4G). O Vite faz proxy da API — não precisa túnel na porta 8000.

## Cores de marca

- Navy: `#003366`
- Cyan: `#00D2FF`
- Dark mode obrigatório (toggle no shell)

## Rotas

Ver tabela completa em [README-MIGRATION.md](../README-MIGRATION.md).

Resumo: auth (login, MFA, reset, ativação), dashboards RM/tenant, listagens admin, perfil/sessões, billing stub. Módulos FTTH, Alertas e OLT abrem via links SSR no hub.
