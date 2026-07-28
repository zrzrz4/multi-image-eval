#!/usr/bin/env bash
# Fast bulk download via hf-mirror + hfd (aria2/wget multi-connection).
# Usage: scripts/download_dataset_hfd.sh <benchmark_id> [--threads N]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MULTI_IMAGE_EVAL_ROOT="$ROOT"

BENCHMARK="${1:-multibanana}"
THREADS="${HF_HFD_THREADS:-10}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --threads)
      THREADS="${2:-8}"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

case "$BENCHMARK" in
  multibanana)
    HF_REPO="kohsei/MultiBanana-Benchmark"
    ;;
  *)
    echo "No hfd repo configured for: $BENCHMARK" >&2
    exit 1
    ;;
esac

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
LOCAL_DIR="$ROOT/data/$BENCHMARK/hf_repo"
LOG="$ROOT/logs/download_${BENCHMARK}_hfd.log"
HFD_DIR="$ROOT/.cache/hfd"
HFD="$HFD_DIR/hfd.sh"

mkdir -p "$ROOT/logs" "$LOCAL_DIR" "$HFD_DIR"

if [[ ! -x "$HFD" ]]; then
  echo "[hfd] fetching hfd.sh from $HF_ENDPOINT"
  curl -fsSL "$HF_ENDPOINT/hfd/hfd.sh" -o "$HFD"
  chmod +x "$HFD"
fi

echo "[hfd] repo=$HF_REPO threads=$THREADS endpoint=$HF_ENDPOINT"
[[ -n "${HF_TOKEN:-}" ]] && echo "[hfd] HF_TOKEN set"
echo "[hfd] local_dir=$LOCAL_DIR"
echo "[log] $LOG"

HFD_ENV=(HF_ENDPOINT="$HF_ENDPOINT")
[[ -n "${HF_TOKEN:-}" ]] && HFD_ENV+=(HF_TOKEN="$HF_TOKEN" HUGGING_FACE_HUB_TOKEN="$HF_TOKEN")

nohup env "${HFD_ENV[@]}" "$HFD" "$HF_REPO" \
  --dataset \
  --tool wget \
  -x "$THREADS" \
  --local-dir "$LOCAL_DIR" \
  >>"$LOG" 2>&1 &

echo "[pid] $!"
echo "tail -f $LOG"
