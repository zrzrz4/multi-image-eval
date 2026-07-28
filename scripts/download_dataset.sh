#!/usr/bin/env bash
# Download dataset for any benchmark: scripts/download_dataset.sh <benchmark_id> [--full|--smoke N]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MULTI_IMAGE_EVAL_ROOT="$ROOT"

BENCHMARK="${1:-}"
if [[ -z "$BENCHMARK" ]]; then
  echo "Usage: $0 <benchmark_id> [--full | --smoke N]" >&2
  exit 1
fi
shift || true

FULL=0
SAMPLES_PER_TASK=2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full)
      FULL=1
      shift
      ;;
    --smoke)
      FULL=0
      SAMPLES_PER_TASK="${2:-2}"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ "$FULL" -eq 1 ]]; then
  SAMPLES_PER_TASK=0
fi

MANIFEST="$ROOT/benchmarks/$BENCHMARK/manifest.json"
if [[ ! -f "$MANIFEST" ]]; then
  echo "Benchmark not found: $BENCHMARK" >&2
  exit 1
fi

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

PYTHON="${MULTI_IMAGE_EVAL_PYTHON:-python3}"
SCRIPT="$ROOT/benchmarks/$BENCHMARK/download_data.py"
if [[ ! -f "$SCRIPT" ]]; then
  echo "No download script for $BENCHMARK ($SCRIPT)" >&2
  exit 1
fi

LOG="$ROOT/logs/download_${BENCHMARK}.log"
mkdir -p "$ROOT/logs"

echo "[download] $BENCHMARK samples_per_task=$SAMPLES_PER_TASK -> data/$BENCHMARK"
echo "[log] $LOG"

nohup "$PYTHON" "$SCRIPT" --samples-per-task "$SAMPLES_PER_TASK" >>"$LOG" 2>&1 &
echo "[pid] $!"
echo "tail -f $LOG"
