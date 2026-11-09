#!/bin/bash
# Retenção LGPD — caches de geocoding/viabilidade (RELATORIO-P2 / P3)
# Crontab exemplo: 0 3 * * 0 /var/www/saas-viabilidade/scripts/cron-purge-caches.sh

set -e
APP_DIR="${APP_DIR:-/var/www/saas-viabilidade}"
cd "$APP_DIR"
DAYS="${CACHE_RETENTION_DAYS:-90}"

if [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

python manage.py purge_geocoding_cache --days="$DAYS"
python manage.py purge_old_caches --days="$DAYS"
echo "purge geocoding + purge_old_caches OK ($(date -Iseconds))"
