"""Build console viewer payload for Edit-Compass Part5 job outputs."""

from __future__ import annotations

import json
import math
from pathlib import Path

from core.paths import PROJECT_ROOT, rel_to_viewer_path, resolve_viewer_image

from benchmarks.edit_compass_part5.data_utils import (
    METRIC_FIELDS,
    METRICS,
    PART5_TASKS,
    TASK_LABELS,
    load_task_items,
)


def _rel_output(path: Path, *, archive_base: Path | None = None) -> str:
    return rel_to_viewer_path(path, archive_base=archive_base)


def _ref_path(data_root: Path, rel: str) -> str:
    p = Path(rel)
    if not p.is_absolute():
        p = data_root / rel
    try:
        return str(p.resolve().relative_to(data_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(p.resolve())


def _item_score(metrics: dict[str, float | None]) -> float | None:
    ia, vc, vq = [], [], []
    for metric, score in metrics.items():
        if score is None:
            return None
        if metric in {"IF"}:
            ia.append(score)
        elif metric in {"URC", "IC"}:
            vc.append(score)
        elif metric == "VQ":
            vq.append(score)
    if not vc:
        return None
    scores = ia + vc + vq
    if not scores:
        return None
    min_score = min(scores)
    if min_score <= 1:
        return min_score
    avg = lambda xs: sum(xs) / len(xs)
    return round(avg(ia) ** 0.4 * avg(vc) ** 0.4 * avg(vq) ** 0.2, 3)


def _load_metric_rows(save_dir: Path, task: str, metric: str) -> dict[str, dict]:
    path = save_dir / f"{task}_{metric}.json"
    if not path.is_file() or path.stat().st_size < 2:
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    if not isinstance(rows, list):
        return {}
    out = {}
    field = METRIC_FIELDS[metric]
    for row in rows:
        if row.get(f"eval_{metric}_status") != "Success":
            continue
        parsed = row.get(field) or {}
        if isinstance(parsed, dict) and "score" in parsed:
            out[str(row["save_id"])] = parsed
    return out


def build_payload(
    data_root: Path,
    output_dir: Path,
    *,
    model_folder: str,
    model_label: str,
    language: str = "en",
    job_label: str | None = None,
    judge_model: str | None = None,
    dimensions: list[dict] | None = None,
    score_scale: int | float = 10,
    archive_base: Path | None = None,
) -> dict:
    save_root = output_dir / model_folder / language
    items: list[dict] = []
    task_stats: dict[str, dict] = {}
    judged_scores: list[float] = []

    for task in PART5_TASKS:
        cfg_dir = save_root / "Part5" / task
        metric_rows = {m: _load_metric_rows(cfg_dir, task, m) for m in METRICS}
        source_rows = load_task_items(data_root, task)
        task_judged = 0

        for row in source_rows:
            save_id = str(row["save_id"])
            png = cfg_dir / f"{save_id}.png"
            if not png.is_file():
                continue

            refs = [row["source_image"], *row.get("reference_image_path", [])]
            refs = [_ref_path(data_root, p) for p in refs]
            prompt_key = f"prompt_{language}"
            instruction = row.get(prompt_key) or row.get(f"prompt_{language}_2", "")

            scores: dict[str, float | None] = {}
            for metric in METRICS:
                if not row.get(metric):
                    continue
                parsed = metric_rows[metric].get(save_id)
                scores[metric.lower()] = parsed.get("score") if parsed else None

            overall = _item_score({k.upper(): v for k, v in scores.items() if k})
            if overall is not None and not math.isnan(overall):
                task_judged += 1
                judged_scores.append(overall)

            entry = {
                "key": f"{task}_{save_id}",
                "task": task,
                "instruction": instruction,
                "references": refs,
                "model_output": _rel_output(png, archive_base=archive_base),
                "model_label": model_label,
                "model_scores": {
                    **{k: v for k, v in scores.items() if v is not None},
                    "score": overall,
                },
            }
            items.append(entry)

        task_stats[task] = {
            "total": len(source_rows),
            "judged": task_judged,
            "label": TASK_LABELS.get(task, task),
        }

    avg = round(sum(judged_scores) / len(judged_scores), 3) if judged_scores else None
    return {
        "benchmark": "edit_compass_part5",
        "title": "Edit-Compass Part5",
        "job_id": job_label,
        "language": language,
        "model_label": model_label,
        "judge_model": judge_model,
        "dimensions": dimensions or [],
        "score_scale": score_scale,
        "items": items,
        "task_stats": task_stats,
        "model_avg_score": avg,
        "judged_total": len(judged_scores),
        "total": sum(ts["total"] for ts in task_stats.values()),
    }
