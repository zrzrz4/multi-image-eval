"""Trim sample galleries for console UI (benchmark-agnostic)."""

from __future__ import annotations

from collections import defaultdict


def trim_samples(
    items: list[dict],
    *,
    task: str = "",
    per_task_all: int = 3,
    per_task_filtered: int = 6,
    max_total: int = 120,
) -> tuple[list[dict], bool]:
    """Return (trimmed_items, was_truncated)."""
    if not items:
        return [], False

    if task and task != "all":
        pool = [i for i in items if i.get("task") == task]
        limit = per_task_filtered
    else:
        pool = list(items)
        limit = per_task_all

    if task and task != "all":
        trimmed = pool[:limit]
        return trimmed, len(pool) > len(trimmed)

    per_task: dict[str, list[dict]] = defaultdict(list)
    for item in pool:
        per_task[item.get("task", "unknown")].append(item)

    trimmed: list[dict] = []
    for task_items in per_task.values():
        trimmed.extend(task_items[:limit])

    trimmed.sort(key=lambda x: (x.get("task", ""), x.get("key", "")))
    if len(trimmed) > max_total:
        trimmed = trimmed[:max_total]
    return trimmed, len(pool) > len(trimmed)
