#!/usr/bin/env python3
"""Export MultiBanana eval results to viewer JSON."""

from __future__ import annotations

import argparse
import json
import socket
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from paths import MULTIBANANA_DATA, PROJECT_ROOT, VIEWER_DATA_DIR  # noqa: E402
from core.paths import rel_to_viewer_path  # noqa: E402

def load_metadata(data_root: Path) -> list[dict]:
    meta_path = data_root / "metadata.json"
    if not meta_path.exists():
        return []
    return json.loads(meta_path.read_text(encoding="utf-8"))

DIM_KEYS = [
    "instruction_alignment",
    "reference_consistency",
    "background_subject_match",
    "physical_realism",
    "visual_quality",
]


def rel_output_path(output_dir: Path, *, archive_base: Path | None = None) -> str:
    return rel_to_viewer_path(output_dir, archive_base=archive_base)


def build_payload(
    data_root: Path,
    output_dir: Path,
    *,
    model_label: str = "FireRed",
    job_label: str | None = None,
    judge_model: str | None = None,
    dimensions: list[dict] | None = None,
    score_scale: int | float = 10,
    archive_base: Path | None = None,
    scope_meta: list[dict] | None = None,
) -> dict:
    meta = load_metadata(data_root) if scope_meta is None else scope_meta
    eval_path = output_dir / "eval_multibanana.json"
    scores_by_key: dict[str, dict] = {}
    eval_data: dict = {}
    if eval_path.exists():
        eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
        scores_by_key = {row["key"]: row for row in eval_data.get("rows", [])}

    out_rel = rel_output_path(output_dir, archive_base=archive_base)
    items = []
    task_scores: dict[str, list[float]] = defaultdict(list)
    dim_totals: dict[str, list[float]] = {k: [] for k in DIM_KEYS}
    judged = 0

    if not meta and scores_by_key:
        # Public archive / smoke runs: metadata may be absent; use eval summary + jpgs.
        for key, row in scores_by_key.items():
            gen_path = output_dir / f"{key}.jpg"
            if not gen_path.is_file():
                continue
            gen_rel = f"{out_rel}/{key}.jpg"
            task = row.get("task") or key.rsplit("_", 1)[0]
            entry = {
                "key": key,
                "task": task,
                "instruction": row.get("instruction", ""),
                "difficulty": row.get("difficulty"),
                "references": [],
                "model_output": gen_rel,
                "model_label": model_label,
                "firered": gen_rel,
                "firered_label": model_label,
                "num_references": 0,
            }
            judged += 1
            model_scores = {k: row[k] for k in DIM_KEYS if k in row}
            model_scores["key"] = key
            model_scores["task"] = task
            model_scores["score"] = row.get("score")
            entry["model_scores"] = model_scores
            entry["firered_scores"] = model_scores
            task_scores[task].append(row.get("score") or 0)
            for dim in DIM_KEYS:
                if dim in row:
                    dim_totals[dim].append(row[dim])
            items.append(entry)
    else:
        for item in meta:
            key = item["key"]
            refs = [
                f"data/multibanana/{p}" if not str(p).startswith("data/multibanana/") else str(p)
                for p in item["reference_paths"]
            ]
            gen_rel = f"{out_rel}/{key}.jpg"
            row = scores_by_key.get(key)
            entry = {
                "key": key,
                "task": item["task"],
                "instruction": item["instruction"],
                "difficulty": item.get("difficulty"),
                "references": refs,
                "model_output": gen_rel,
                "model_label": model_label,
                "firered": gen_rel,
                "firered_label": model_label,
                "num_references": len(refs),
            }
            if row:
                judged += 1
                model_scores = {k: row[k] for k in DIM_KEYS if k in row}
                model_scores["key"] = key
                model_scores["task"] = item["task"]
                model_scores["score"] = row.get("score")
                entry["model_scores"] = model_scores
                entry["firered_scores"] = model_scores
                task_scores[item["task"]].append(row["score"])
                for dim in DIM_KEYS:
                    if dim in row:
                        dim_totals[dim].append(row[dim])
            items.append(entry)

    total = len(items)
    avg = round(sum(r["score"] for rows in scores_by_key.values() for r in [rows]) / len(scores_by_key), 3) if scores_by_key else None
    dim_avg = {
        dim: round(sum(vals) / len(vals), 2) if vals else None
        for dim, vals in dim_totals.items()
    }
    task_stats = {
        task: {
            "firered_avg": round(sum(vals) / len(vals), 2),
            "total": sum(1 for i in items if i["task"] == task),
            "judged": len(vals),
        }
        for task, vals in task_scores.items()
    }
    for item in items:
        if item["task"] not in task_stats:
            task_stats[item["task"]] = {
                "firered_avg": 0,
                "total": sum(1 for i in items if i["task"] == item["task"]),
                "judged": 0,
            }

    host = socket.gethostname()
    label = job_label or output_dir.name
    return {
        "benchmark": "multibanana",
        "eval_mode": "multibanana",
        "title": "MultiBanana",
        "subtitle": (
            f"多参考图文生图 · {model_label} @ {host} · "
            f"已评测 {judged}/{total} 条 · {label}"
        ),
        "firered_name": model_label,
        "model_label": model_label,
        "judge_model": judge_model,
        "has_baseline": False,
        "total": total,
        "judged_total": judged,
        "model_avg_score": avg,
        "firered_avg_score": avg,
        "score_scale": score_scale,
        "dimensions": dimensions or [
            {"key": k, "label": k} for k in DIM_KEYS
        ],
        "dimension_avg": dim_avg,
        "task_stats": task_stats,
        "methodology_notes": [
            {
                "title": "数据来源",
                "body": (
                    f"参考图来自 HF MultiBanana-Benchmark；生成与 Gemini 评测在 {host} 上运行。"
                    " 本项目路径：~/work/multi-image-eval"
                ),
                "link": "https://github.com/matsuolab/multibanana",
                "link_label": "MultiBanana",
            }
        ],
        "items": items,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": out_rel,
    }


def export(*args, **kwargs) -> dict:
    """Backward-compatible alias."""
    return build_payload(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=str(MULTIBANANA_DATA))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--out", default=str(VIEWER_DATA_DIR / "multibanana.json"))
    parser.add_argument("--model-label", default="FireRed")
    parser.add_argument("--firered-name", default="", help=argparse.SUPPRESS)
    parser.add_argument("--job-label", default="")
    args = parser.parse_args()

    model_label = args.model_label or args.firered_name or "FireRed"
    payload = build_payload(
        Path(args.data_root),
        Path(args.output_dir),
        model_label=model_label,
        job_label=args.job_label or None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[export] {out} · judged {payload['judged_total']}/{payload['total']} · avg {payload['firered_avg_score']}")


if __name__ == "__main__":
    main()
