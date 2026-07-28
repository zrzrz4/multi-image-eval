"""Recompute viewer aggregate scores from item rows (task-filter aware)."""

from __future__ import annotations

from collections import defaultdict


def _item_scores(item: dict) -> dict:
    return item.get("model_scores") or item.get("firered_scores") or {}


def compute_viewer_stats(items: list[dict], *, task: str = "") -> dict:
    """Return avg / judged counts / task_stats for all items or one task."""
    pool = items if not task else [i for i in items if i.get("task") == task]
    judged_scores: list[float] = []
    task_scores: dict[str, list[float]] = defaultdict(list)
    dim_totals: dict[str, list[float]] = defaultdict(list)

    for item in pool:
        scores = _item_scores(item)
        overall = scores.get("score")
        if overall is None:
            continue
        judged_scores.append(float(overall))
        task_scores[item.get("task") or "unknown"].append(float(overall))
        for key, val in scores.items():
            if key in ("key", "task", "score") or not isinstance(val, (int, float)):
                continue
            dim_totals[key].append(float(val))

    avg = round(sum(judged_scores) / len(judged_scores), 3) if judged_scores else None
    tasks_in_pool = {i.get("task") for i in pool if i.get("task")}
    task_stats: dict[str, dict] = {}
    for task_id in sorted(tasks_in_pool):
        vals = task_scores.get(task_id, [])
        task_stats[task_id] = {
            "firered_avg": round(sum(vals) / len(vals), 2) if vals else 0,
            "total": sum(1 for i in pool if i.get("task") == task_id),
            "judged": len(vals),
        }

    dim_avg = {
        dim: round(sum(vals) / len(vals), 2) if vals else None
        for dim, vals in dim_totals.items()
    }

    return {
        "model_avg_score": avg,
        "firered_avg_score": avg,
        "judged_total": len(judged_scores),
        "total": len(pool),
        "task_stats": task_stats,
        "dimension_avg": dim_avg,
    }
