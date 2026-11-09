#!/usr/bin/env bash
# Cron LGPD — exclusão/anonimização automática (diário 03:00)
set -euo pipefail
cd "$(dirname "$0")/.."
export DJANGO_SETTINGS_MODULE=saas_viabilidade.settings
python manage.py process_data_subject_requests --notify
python manage.py purge_activation_tokens 2>/dev/null || true
