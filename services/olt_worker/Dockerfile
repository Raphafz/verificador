# Imagem do worker OLT — rede isolada (OpenVPN/L2TP) por container/job.
# Build na raiz do repo: ./scripts/build-olt-worker.sh

FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    openvpn \
    iproute2 \
    iputils-ping \
    strongswan \
    xl2tpd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=saas_viabilidade.settings

# Entrypoint: python manage.py olt_run_job --job-id N --operation list|delete
ENTRYPOINT ["python", "manage.py"]
