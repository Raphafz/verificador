# Legacy (SSR Django)

Templates e assets do front-end server-rendered são movidos para cá **somente após**
paridade E2E validada no React (`/frontend`).

**Política:** nunca deletar — apenas mover e desativar rotas HTML via `FRONTEND_MODE`.

Durante a migração incremental (Strangler Fig), o SSR permanece em `templates/` e `static/`
até cada módulo ser validado.
