#!/usr/bin/env bash
# Retenção LGPD global — diário 04:00
set -euo pipefail
cd "$(dirname "$0")/.."
export DJANGO_SETTINGS_MODULE=saas_viabilidade.settings
python manage.py purge_lgpd_retention
python manage.py lgpd_compliance_report --format json --output logs/lgpd-report-$(date +%Y%m%d).json
