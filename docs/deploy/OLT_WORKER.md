# OLT Worker — deploy em produção (VPN multi-tenant)

## Problema

Várias empresas com VPN na mesma VPS não podem compartilhar uma única rota VPN no host. O modo **container** isola cada job em um network namespace próprio.

## Arquitetura

```text
Gunicorn (Django)
    → dispatch_job()
        → docker run (cap NET_ADMIN, /dev/net/tun)
            → manage.py olt_run_job
                → OpenVPN dentro do container
                → SSH/Telnet na OLT
                → log no PostgreSQL
```

## Passo a passo (VPS Linux)

### 1. Instalar Docker

```bash
apt update && apt install -y docker.io
usermod -aG docker www-data   # ou usuário do gunicorn
```

### 2. Build da imagem

```bash
cd /var/www/saas-viabilidade
./scripts/build-olt-worker.sh
```

### 3. `.env` do Django

```env
OLT_EXECUTION_MODE=container
OLT_WORKER_IMAGE=rmsys/olt-worker:latest
OLT_MAX_PARALLEL_JOBS=5
FIELD_ENCRYPTION_KEY=...   # obrigatório — senhas OLT/VPN
DATABASE_URL=...
```

Se o PostgreSQL escuta só em `127.0.0.1`, no Linux use:

```env
OLT_DOCKER_RUN_ARGS=--network=host
```

### 4. Reiniciar Gunicorn

```bash
sudo systemctl restart gunicorn
```

### 5. Por empresa (Admin Django)

**Execução OLT da empresa**:
- Modo vazio = global
- `container` = forçar container
- `host` = legado (mutex VPN no host)
- Jobs paralelos máx. = limite por ISP

## Modo host (legado / dev Windows)

```env
OLT_EXECUTION_MODE=host
```

- Uma VPN ativa por vez no host (`olt:host:vpn_mutex` via cache/Redis).
- Jobs entram na **fila** (`status=queued`) quando o slot está ocupado; a UI mostra mensagem amigável.

## Checklist produção (P0-O01)

- [ ] Docker instalado e usuário do Gunicorn no grupo `docker`
- [ ] `./scripts/build-olt-worker.sh` executado na VPS
- [ ] `.env`: `OLT_EXECUTION_MODE=container`
- [ ] `FIELD_ENCRYPTION_KEY` definida (senhas OLT/VPN)
- [ ] Gunicorn reiniciado
- [ ] Teste: job OLT com VPN em empresa piloto

## Monitoramento

```bash
docker ps --filter label=rmsys.service=olt-worker
docker logs olt-job-123   # se --rm não aplicável durante execução
```

## Firewall

Saída UDP permitida para OpenVPN (1194/4500) e IPsec.

## Troubleshooting

| Sintoma | Ação |
|--------|------|
| `Docker não encontrado` | Instalar Docker ou voltar `OLT_EXECUTION_MODE=host` |
| Container não alcança DB | `OLT_DOCKER_RUN_ARGS=--network=host` |
| L2TP falha no container | `OLT_DOCKER_RUN_ARGS=--privileged` |
| Limite paralelo | Aumentar `OLT_MAX_PARALLEL_JOBS` ou reduzir carga |
