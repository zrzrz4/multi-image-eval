#!/usr/bin/env python3
"""Download MultiBanana official dataset (smoke or full)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.env import apply_dotenv  # noqa: E402

apply_dotenv()

from benchmarks.multibanana.data_utils import estimate_dataset_stats, hf_endpoint, setup_subset  # noqa: E402
from paths import MULTIBANANA_DATA  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Download MultiBanana dataset from HuggingFace")
    parser.add_argument("--data-root", default=str(MULTIBANANA_DATA))
    parser.add_argument("--samples-per-task", type=int, default=0, help="0 = full dataset per task type")
    parser.add_argument("--smoke", type=int, default=0, help="Shortcut: N samples per task (overrides --samples-per-task)")
    args = parser.parse_args()

    per_task = args.smoke if args.smoke > 0 else args.samples_per_task
    data_root = Path(args.data_root)

    ep = hf_endpoint() or "huggingface.co (official)"
    print(f"[hf] endpoint={ep}")
    est = estimate_dataset_stats(per_task)
    print(f"[plan] {est['label']} · {est['task_count']} classes · ~{est['total_samples']} samples")

    items = setup_subset(data_root, samples_per_task=per_task)
    print(f"[done] metadata written: {len(items)} items -> {data_root / 'metadata.json'}")


if __name__ == "__main__":
    main()
