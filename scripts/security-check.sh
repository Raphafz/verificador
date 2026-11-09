#!/usr/bin/env bash
# Varredura rápida de padrões inseguros (DevSecOps local/CI)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Secret / pattern scan ==="
FAIL=0
PATTERNS=(
  'dev-secret-key-change-me'
  'django-insecure-'
  'password\s*=\s*["\x27][^"\x27]{3,}'
  'BEGIN (RSA |OPENSSH )?PRIVATE KEY'
)

for pat in "${PATTERNS[@]}"; do
  if rg -n --glob '!.env' --glob '!*.md' --glob '!.git/**' -i "$pat" 2>/dev/null | head -5; then
    echo "WARN: possível segredo/padrão: $pat"
    FAIL=1
  fi
done

echo "=== .env não deve estar versionado ==="
if git ls-files --error-unmatch .env 2>/dev/null; then
  echo "FAIL: .env está no git"
  FAIL=1
else
  echo "OK"
fi

exit $FAIL
