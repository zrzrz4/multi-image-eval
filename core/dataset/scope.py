"""Filter dataset items by console params (task types, per-class limits)."""

from __future__ import annotations

from collections import defaultdict

from core.dataset.params import resolve_samples_per_task
from core.dataset.stats import normalize_task_types


def scope_items_by_params(
    items: list[dict],
    params: dict,
    *,
    task_key: str = "task",
    sort_key: str = "key",
    apply_samples_limit: bool = True,
) -> list[dict]:
    """Return items limited to job params (selected task types + optional samples_per_task)."""
    task_types = normalize_task_types(params.get("task_types"))
    samples = resolve_samples_per_task(params) if apply_samples_limit else 0
    if task_types:
        allowed = set(task_types)
        items = [i for i in items if i.get(task_key) in allowed]
    if samples > 0:
        counts: dict[str, int] = defaultdict(int)
        scoped: list[dict] = []
        for item in sorted(items, key=lambda x: (x.get(task_key, ""), x.get(sort_key, ""))):
            task = item.get(task_key, "")
            if counts[task] >= samples:
                continue
            counts[task] += 1
            scoped.append(item)
        items = scoped
    return items
