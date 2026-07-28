#!/usr/bin/env bash
# Fast parallel download: N shards × M workers (target ~30–60 min for 8.9GB).
# Usage: scripts/download_dataset_fast.sh multibanana [--shards 8] [--workers 48]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MULTI_IMAGE_EVAL_ROOT="$ROOT"

BENCHMARK="${1:-multibanana}"
SHARDS="${HF_PARALLEL_SHARDS:-8}"
WORKERS="${HF_DOWNLOAD_WORKERS:-48}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --shards) SHARDS="${2:-8}"; shift 2 ;;
    --workers) WORKERS="${2:-48}"; shift 2 ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
done

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
PYTHON="${MULTI_IMAGE_EVAL_PYTHON:-python3}"
LOCAL_DIR="$ROOT/data/$BENCHMARK/hf_repo"
LOG_DIR="$ROOT/logs/download_${BENCHMARK}_fast"
SCRIPT="$ROOT/benchmarks/multibanana/download_parallel.py"

mkdir -p "$LOG_DIR" "$LOCAL_DIR"

# Stop legacy single-threaded hfd jobs for this dataset.
pkill -f "hfd.sh kohsei/MultiBanana-Benchmark" 2>/dev/null || true
pkill -f "wget.*hfd/wget_urls" 2>/dev/null || true
sleep 1

echo "[fast] benchmark=$BENCHMARK shards=$SHARDS workers/shard=$WORKERS"
echo "[fast] local_dir=$LOCAL_DIR endpoint=$HF_ENDPOINT"

for ((i = 0; i < SHARDS; i++)); do
  LOG="$LOG_DIR/shard${i}.log"
  nohup env PARALLEL_SHARD="$i" PARALLEL_SHARDS="$SHARDS" HF_DOWNLOAD_WORKERS="$WORKERS" \
    "$PYTHON" "$SCRIPT" --local-dir "$LOCAL_DIR" --shard "$i" --shards "$SHARDS" --workers "$WORKERS" \
    >>"$LOG" 2>&1 &
  echo "[shard $i] pid=$! log=$LOG"
done

echo "tail -f $LOG_DIR/shard0.log"
