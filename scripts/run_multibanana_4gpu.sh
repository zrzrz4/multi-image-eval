#!/usr/bin/env bash
# Launch 4-GPU MultiBanana smoke (one shard per GPU).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JOB_ID="${JOB_ID:-smoke_$(date +%Y%m%d_%H%M%S)}"
OUTPUT_DIR="$ROOT/outputs/multibanana/${JOB_ID}"
LOG_DIR="$ROOT/logs"
GEN_VENV="${GEN_VENV:-$ROOT/.venvs/gen/bin/python}"

mkdir -p "$OUTPUT_DIR" "$ROOT/logs"
export MULTI_IMAGE_EVAL_ROOT="$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

PYTHON="${MULTI_IMAGE_EVAL_PYTHON:-$GEN_VENV}"
if [[ -x "$PYTHON" ]]; then PY="$PYTHON"; else PY="python3"; fi

"$PY" "$ROOT/benchmarks/multibanana/run.py" \
  --setup-data \
  --samples-per-task "${SAMPLES_PER_TASK:-2}" \
  --output-dir "$OUTPUT_DIR" \
  --gen-only \
  --parallel-shards 4 \
  --parallel-shard 0 || true

for SHARD in 0 1 2 3; do
  CUDA_VISIBLE_DEVICES="$SHARD" nohup "$PY" "$ROOT/benchmarks/multibanana/run.py" \
    --output-dir "$OUTPUT_DIR" \
    --parallel-shard "$SHARD" \
    --parallel-shards 4 \
    >"$LOG_DIR/multibanana_shard${SHARD}.log" 2>&1 &
  echo "[launch] shard $SHARD -> GPU $SHARD (pid $!)"
done

ln -sfn "$JOB_ID" "$ROOT/outputs/multibanana/latest"
echo "[job] $JOB_ID -> $OUTPUT_DIR"
echo "[monitor] tail -f $LOG_DIR/multibanana_shard*.log"
