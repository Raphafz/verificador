#!/usr/bin/env bash
# DevSecOps — auditoria local
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== pip audit (opcional) ==="
pip audit 2>/dev/null || echo "pip-audit não instalado — pip install pip-audit"

echo "=== Django check ==="
python manage.py check

echo "=== scan_security --strict ==="
python manage.py scan_security --strict

echo "=== check_deploy ==="
python manage.py check_deploy

echo "=== LGPD compliance (texto) ==="
python manage.py lgpd_compliance_report --dpia

echo "OK"
