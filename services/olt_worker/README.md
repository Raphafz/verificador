# OLT Worker (container)

Worker efêmero que executa jobs OLT com **VPN isolada** por container.

## Build

Na raiz do repositório:

```bash
./scripts/build-olt-worker.sh
# ou: docker build -f services/olt_worker/Dockerfile -t rmsys/olt-worker:latest .
```

## Uso manual

```bash
docker run --rm \
  --cap-add=NET_ADMIN \
  --device=/dev/net/tun \
  --add-host=host.docker.internal:host-gateway \
  -e DATABASE_URL="..." \
  -e SECRET_KEY="..." \
  -e FIELD_ENCRYPTION_KEY="..." \
  rmsys/olt-worker:latest \
  olt_run_job --job-id 123 --operation list
```

## Django

Configure no `.env`:

```env
OLT_EXECUTION_MODE=container
OLT_WORKER_IMAGE=rmsys/olt-worker:latest
OLT_MAX_PARALLEL_JOBS=5
```

Por empresa (opcional): Admin → **Execução OLT da empresa** — modo e limite paralelo.

## Notas

- **OpenVPN** funciona bem no container.
- **L2TP/IPsec** pode exigir `--privileged` ou `OLT_DOCKER_RUN_ARGS=--privileged` (xl2tpd).
- PostgreSQL no host: use `--add-host=host.docker.internal:host-gateway` (já incluído no dispatcher) ou `OLT_DOCKER_RUN_ARGS=--network=host` no Linux.
