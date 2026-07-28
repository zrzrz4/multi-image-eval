"""Edit-Compass Part5 dataset helpers."""

from __future__ import annotations

import json
import random
from pathlib import Path

PART5_TASKS = [
    "Multi_Image_Aware",
    "Multi_Image_Composition",
    "Virtual_Try_On",
]

TASK_LABELS = {
    "Multi_Image_Aware": "多图感知",
    "Multi_Image_Composition": "多图合成",
    "Virtual_Try_On": "虚拟试穿",
}

TASK_TOTALS = {
    "Multi_Image_Aware": 78,
    "Multi_Image_Composition": 49,
    "Virtual_Try_On": 60,
}

METRICS = ("IF", "IC", "URC", "VQ")
METRIC_FIELDS = {
    "IF": "Instrcution_Following",
    "IC": "Identity_Consistency",
    "URC": "Unedited_Region_Consistency",
    "VQ": "Visual_Quality",
}


def task_json_path(data_root: Path, task: str) -> Path:
    return data_root / "Part5" / task / f"{task}.json"


def load_task_items(data_root: Path, task: str) -> list[dict]:
    path = task_json_path(data_root, task)
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_items(data_root: Path, task_types: list[str] | None = None) -> list[dict]:
    tasks = task_types or PART5_TASKS
    items: list[dict] = []
    for task in tasks:
        if task not in PART5_TASKS:
            continue
        for row in load_task_items(data_root, task):
            items.append({
                **row,
                "task": task,
                "key": f"{task}_{row['save_id']}",
            })
    return items


def scope_items(
    data_root: Path,
    *,
    task_types: list[str] | None = None,
    subset: int = 0,
    seed: int = 42,
) -> list[dict]:
    tasks = task_types or PART5_TASKS
    out: list[dict] = []
    for task in tasks:
        rows = load_task_items(data_root, task)
        if subset > 0 and subset < len(rows):
            rng = random.Random(seed + hash(task) % (2**31))
            rows = rng.sample(rows, subset)
        for row in rows:
            out.append({**row, "task": task, "key": f"{task}_{row['save_id']}"})
    return out


def dataset_stats(data_root: Path, params: dict) -> dict:
    task_types = params.get("task_types") or []
    tasks = [t for t in (task_types or PART5_TASKS) if t in PART5_TASKS]
    subset = int(params.get("samples_per_task") or 0)
    items = scope_items(data_root, task_types=tasks, subset=subset, seed=int(params.get("seed", 42)))
    per_task = {}
    for item in items:
        per_task[item["task"]] = per_task.get(item["task"], 0) + 1
    total_full = sum(TASK_TOTALS.get(t, 0) for t in tasks)
    label = "全量 Part5" if subset <= 0 else f"每类 {subset} 条（smoke）"
    return {
        "label": label,
        "task_count": len(tasks),
        "total_samples": len(items),
        "metadata_total": total_full,
        "per_task": per_task,
        "source": "edit_compass_part5",
    }
