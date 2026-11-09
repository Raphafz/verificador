#!/usr/bin/env bash
# Scan CASCAVEL contra RM Systems (local/staging).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
CASCAVEL_DIR="${CASCAVEL_DIR:-$ROOT/tools/Cascavel}"
PROFILE="${PROFILE:-rmsys}"
REPORTS_DIR="$ROOT/reports/cascavel"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SKIP_SERVER_CHECK="${SKIP_SERVER_CHECK:-0}"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export NO_COLOR=1

# host:port para CASCAVEL (sem http://)
CASCAVEL_TARGET="${CASCAVEL_TARGET:-$(echo "$BASE_URL" | sed -E 's#^https?://##' | cut -d/ -f1)}"

mkdir -p "$REPORTS_DIR"

echo "== RM Systems × CASCAVEL =="
echo "BASE_URL: $BASE_URL"
echo "CASCAVEL target: $CASCAVEL_TARGET"
echo ""

if [[ "$SKIP_SERVER_CHECK" != "1" ]]; then
  curl -sf --max-time 10 "$BASE_URL/health/" >/dev/null || {
    echo "ERRO: Django offline. Rode: python manage.py runserver"
    exit 1
  }
fi

[[ -f "$CASCAVEL_DIR/cascavel.py" ]] || {
  echo "Clone: git clone https://github.com/glferreira-devsecops/Cascavel.git $CASCAVEL_DIR"
  exit 1
}

cd "$CASCAVEL_DIR"
[[ -d venv ]] || python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements.txt

LOG="$REPORTS_DIR/scan-$TIMESTAMP.log"
set +e
printf '0\n' | python3 cascavel.py -t "$CASCAVEL_TARGET" \
  --allow-localhost \
  --plugins-only \
  --profile "$PROFILE" \
  -q -o json \
  --no-preloader \
  --no-notify \
  --timeout 120 2>&1 | tee "$LOG"
EXIT=$?
set -e

if [[ -d reports ]]; then
  DEST="$REPORTS_DIR/cascavel-export-$TIMESTAMP"
  mkdir -p "$DEST"
  cp -a reports/. "$DEST/" 2>/dev/null || true
  echo "Export: $DEST"
fi

exit "$EXIT"
