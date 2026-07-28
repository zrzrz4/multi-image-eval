#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MULTI_IMAGE_EVAL_ROOT="$ROOT"

OUTPUT_DIR="${1:-$ROOT/outputs/multibanana/latest}"
if [[ -L "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$(readlink -f "$OUTPUT_DIR")"
fi

python3 "$ROOT/benchmarks/multibanana/export_viewer.py" \
  --output-dir "$OUTPUT_DIR" \
  --job-label "$(basename "$OUTPUT_DIR")"
