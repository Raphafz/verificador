#!/usr/bin/env bash
# Build da imagem olt-worker (rede isolada por job OLT).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${OLT_WORKER_IMAGE:-rmsys/olt-worker:latest}"
docker build -f "$ROOT/services/olt_worker/Dockerfile" -t "$IMAGE" "$ROOT"
echo "Imagem pronta: $IMAGE"
