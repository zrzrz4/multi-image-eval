#!/usr/bin/env bash
# Build a clean tarball for GitHub (code + docs only, no secrets).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$ROOT/dist-github/multi-image-eval"
ARCHIVE="$(dirname "$ROOT")/multi-image-eval-github.tar.gz"

rm -rf "$ROOT/dist-github"
mkdir -p "$STAGE"

# Copy tree (rsync optional; fall back to tar pipe)
if command -v rsync >/dev/null 2>&1; then
  RSYNC_EXCLUDES=(
    --exclude '.git/'
    --exclude '.env'
    --exclude 'dist-github/'
    --exclude 'jobs/'
    --exclude 'outputs/'
    --exclude 'logs/'
    --exclude 'data/'
    --exclude 'node_modules/'
    --exclude '.venvs/'
    --exclude '.venv/'
    --exclude 'venv/'
    --exclude '__pycache__/'
    --exclude '*.pyc'
    --exclude 'frontend/console/dist/'
    --exclude 'frontend/eval-viewer/dist/'
    --exclude 'frontend/viewer_data/*.json'
    --exclude '.platform/'
    --exclude 'config/custom_weights.json'
    --exclude '*.tar.gz'
    --exclude 'migrate/export/'
  )
  rsync -a "${RSYNC_EXCLUDES[@]}" "$ROOT/" "$STAGE/"
else
  tar -C "$ROOT" \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='dist-github' \
    --exclude='jobs' \
    --exclude='outputs' \
    --exclude='logs' \
    --exclude='data' \
    --exclude='node_modules' \
    --exclude='.venvs' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='frontend/console/dist' \
    --exclude='frontend/eval-viewer/dist' \
    --exclude='.platform' \
    --exclude='config/custom_weights.json' \
    --exclude='*.tar.gz' \
    --exclude='migrate/export' \
    -cf - . | tar -C "$STAGE" -xf -
fi

# Ensure example env is present (never copy real .env)
if [[ ! -f "$STAGE/.env.example" ]]; then
  echo "[error] missing .env.example in staged tree" >&2
  exit 1
fi

# Scan staged tree for common sensitive patterns
SCAN_FAIL=0
scan_pattern() {
  local label="$1"
  local pattern="$2"
  local hits
  hits=$(grep -RIn \
    --exclude=package_for_github.sh \
    --exclude-dir=node_modules \
    --exclude='*.tar.gz' \
    -E "$pattern" "$STAGE" 2>/dev/null || true)
  if [[ -n "$hits" ]]; then
    echo "[FAIL] sensitive pattern ($label):" >&2
    echo "$hits" | head -20 >&2
    SCAN_FAIL=1
  fi
}

scan_pattern 'internal path cpfs01' '/cpfs[0-9]'
scan_pattern 'internal host gpu-node' 'gpu-node[0-9]'
scan_pattern 'agrouter gateway' 'agrouter'
scan_pattern 'kiwiar domain' 'kiwiar'
scan_pattern 'sk- API key' 'sk-[A-Za-z0-9]{20,}'
scan_pattern 'hf_ token' 'hf_[A-Za-z0-9]{20,}'
scan_pattern 'Bearer token' 'Bearer [A-Za-z0-9._-]{20,}'

# Real .env must not appear
if [[ -f "$STAGE/.env" ]]; then
  echo "[FAIL] .env leaked into staging" >&2
  SCAN_FAIL=1
fi

if [[ "$SCAN_FAIL" -ne 0 ]]; then
  echo "[error] secret scan failed — fix matches before publishing" >&2
  exit 1
fi

tar -czf "$ARCHIVE" -C "$ROOT/dist-github" multi-image-eval
echo "[ok] staged: $STAGE"
echo "[ok] archive: $ARCHIVE"
echo "[ok] secret scan passed"
