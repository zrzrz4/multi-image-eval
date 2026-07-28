"""Compute dataset subset statistics from metadata items."""

from __future__ import annotations

from collections import Counter


def normalize_task_types(task_types) -> list[str]:
    if not task_types:
        return []
    if isinstance(task_types, str):
        return [t.strip() for t in task_types.split(",") if t.strip()]
    return [str(t) for t in task_types if t]


def compute_subset_stats(
    items: list[dict],
    *,
    task_types: list[str] | None = None,
    samples_per_task: int = 0,
    task_key: str = "task",
) -> dict:
    """Return task/sample counts for a filtered subset."""
    allowed = set(task_types or [])
    per_task_all = Counter(item[task_key] for item in items)
    if allowed:
        per_task = {k: v for k, v in per_task_all.items() if k in allowed}
    else:
        per_task = dict(per_task_all)

    if samples_per_task > 0:
        total = sum(min(samples_per_task, n) for n in per_task.values())
        mode = "smoke"
        if allowed:
            label = f"已选 {len(per_task)} 类 · 每类 {samples_per_task} 条"
        else:
            label = f"每类 {samples_per_task} 条（smoke）"
    else:
        if allowed:
            total = sum(1 for item in items if item[task_key] in allowed)
            label = f"已选 {len(per_task)} 类 · 全量"
        else:
            total = len(items)
            label = "全量"

    return {
        "mode": mode if samples_per_task > 0 else "full",
        "label": label,
        "task_count": len(per_task),
        "selected_task_count": len(per_task),
        "total_tasks_available": len(per_task_all),
        "total_samples": total,
        "per_task_max": max(per_task.values()) if per_task else 0,
        "per_task_min": min(per_task.values()) if per_task else 0,
    }
