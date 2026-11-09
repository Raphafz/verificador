# Alert Bridge (worker)

Serviço Node que substitui a pasta legada `MENSAGENS/`. Lê configurações **por empresa** na API do Django.

## Setup

```bash
cd services/alert_bridge
cp .env.example .env
npm install
```

No `.env` do Django (raiz do projeto):

```env
ALERT_BRIDGE_API_TOKEN=seu-token-secreto
```

## Executar

```bash
npm start
```

Configure cada empresa em: `/{slug}/alertas/config/` (módulo Alertas ativo).

## Legado

A pasta `MENSAGENS/` na raiz pode ser removida após migrar o `.env` antigo para o painel web.
