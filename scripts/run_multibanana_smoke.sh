#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MULTI_IMAGE_EVAL_ROOT="$ROOT"

SAMPLES_PER_TASK="${SAMPLES_PER_TASK:-2}"
JOB_ID="${JOB_ID:-smoke_$(date +%Y%m%d_%H%M%S)}"
OUTPUT_DIR="$ROOT/outputs/multibanana/${JOB_ID}"
GEN_VENV="${GEN_VENV:-$ROOT/.venvs/gen/bin/python}"

mkdir -p "$OUTPUT_DIR" "$ROOT/logs"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

PYTHON="${MULTI_IMAGE_EVAL_PYTHON:-$GEN_VENV}"
if [[ -x "$PYTHON" ]]; then PY="$PYTHON"; else PY="python3"; fi
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"

"$PY" "$ROOT/benchmarks/multibanana/run.py" \
  --setup-data \
  --samples-per-task "$SAMPLES_PER_TASK" \
  --output-dir "$OUTPUT_DIR" \
  "$@"

ln -sfn "$JOB_ID" "$ROOT/outputs/multibanana/latest"

python3 "$ROOT/benchmarks/multibanana/export_viewer.py" \
  --output-dir "$OUTPUT_DIR" \
  --job-label "$JOB_ID"

echo "[done] output -> $OUTPUT_DIR"
