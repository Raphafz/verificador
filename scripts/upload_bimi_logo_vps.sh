#!/usr/bin/env bash
# Publica logo.svg BIMI na VPS (Nginx alias em nginx.conf).
# Uso na VPS, após git pull:
#   bash scripts/upload_bimi_logo_vps.sh
#
# Ou copie só o arquivo (substitua USUARIO e caminho):
#   scp static/well-known/bimi/logo.svg USUARIO@31.97.250.236:/var/www/saas-viabilidade/static/well-known/bimi/logo.svg
#   ssh USUARIO@31.97.250.236 'cd /var/www/saas-viabilidade && source venv/bin/activate && python manage.py collectstatic --noinput && sudo systemctl reload nginx'

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/static/well-known/bimi/logo.svg"
DEST_DIR="/var/www/saas-viabilidade/static/well-known/bimi"
STATICFILES="/var/www/saas-viabilidade/staticfiles/well-known/bimi"

if [[ ! -f "$SRC" ]]; then
  echo "Arquivo não encontrado: $SRC"
  exit 1
fi

mkdir -p "$DEST_DIR" "$STATICFILES"
cp "$SRC" "$DEST_DIR/logo.svg"
cp "$SRC" "$STATICFILES/logo.svg"

if [[ -d "$ROOT/venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/venv/bin/activate"
  cd "$ROOT"
  python manage.py collectstatic --noinput
fi

if command -v nginx >/dev/null 2>&1; then
  sudo nginx -t && sudo systemctl reload nginx
fi

echo "OK: logo publicado em $STATICFILES/logo.svg"
echo "Teste: curl -I https://rmsys.com.br/.well-known/bimi/logo.svg"
