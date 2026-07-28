"""MultiBanana dataset helpers."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HF_REPO = "kohsei/MultiBanana-Benchmark"
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]

MULTIBANANA_TASK_TYPES = [
    "3_back", "3_global", "3_local", "3_object",
    "4_back", "4_global", "4_local", "4_object",
    "5_back", "5_global", "5_local", "5_object",
    "6_back", "6_global", "6_local", "6_object",
    "7_back", "7_global", "7_local", "7_object",
    "8_back", "8_global", "8_local", "8_object",
    "add", "background", "color", "hair", "makeup", "material",
    "pose", "replace", "single", "style", "text", "tone",
]

MULTIBANANA_TASK_LABELS = {
    "3_back": "3参考·背景",
    "3_global": "3参考·全局",
    "3_local": "3参考·局部",
    "3_object": "3参考·物体",
    "4_back": "4参考·背景",
    "4_global": "4参考·全局",
    "4_local": "4参考·局部",
    "4_object": "4参考·物体",
    "5_back": "5参考·背景",
    "5_global": "5参考·全局",
    "5_local": "5参考·局部",
    "5_object": "5参考·物体",
    "6_back": "6参考·背景",
    "6_global": "6参考·全局",
    "6_local": "6参考·局部",
    "6_object": "6参考·物体",
    "7_back": "7参考·背景",
    "7_global": "7参考·全局",
    "7_local": "7参考·局部",
    "7_object": "7参考·物体",
    "8_back": "8参考·背景",
    "8_global": "8参考·全局",
    "8_local": "8参考·局部",
    "8_object": "8参考·物体",
    "add": "添加",
    "background": "背景",
    "color": "颜色",
    "hair": "发型",
    "makeup": "妆容",
    "material": "材质",
    "pose": "姿态",
    "replace": "替换",
    "single": "单参考",
    "style": "风格",
    "text": "文字",
    "tone": "色调",
}


def hf_endpoint() -> str | None:
    ep = os.environ.get("HF_ENDPOINT") or os.environ.get("HUGGINGFACE_HUB_ENDPOINT")
    return ep.strip() if ep else None


def download_workers() -> int:
    return max(1, int(os.environ.get("HF_DOWNLOAD_WORKERS", "16")))


def _hf_api():
    from huggingface_hub import HfApi

    ep = hf_endpoint()
    return HfApi(endpoint=ep) if ep else HfApi()


def build_file_index() -> tuple[list[str], dict[str, list[str]], dict[str, set[str]]]:
    api = _hf_api()
    files = api.list_repo_files(HF_REPO, repo_type="dataset")
    task_types = sorted(
        {
            f.split("/")[0]
            for f in files
            if "/" in f and not f.startswith(".") and not f.endswith(".csv")
        }
    )
    by_task: dict[str, list[str]] = defaultdict(list)
    sample_ids: dict[str, set[str]] = defaultdict(set)
    for rel in files:
        if "/" not in rel:
            continue
        task, name = rel.split("/", 1)
        by_task[task].append(name)
        m = re.match(r"^(\d+)_prompt\.txt$", name)
        if m:
            sample_ids[task].add(m.group(1))
    return task_types, by_task, sample_ids


def download_file(rel_path: str, dst: Path, data_root: Path | None = None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    if data_root is not None:
        local = data_root / "hf_repo" / rel_path
        if local.exists():
            dst.write_bytes(local.read_bytes())
            return
    kwargs: dict = {"repo_id": HF_REPO, "filename": rel_path, "repo_type": "dataset"}
    ep = hf_endpoint()
    endpoints: list[str | None] = []
    if ep:
        endpoints.append(ep)
    endpoints.append(None)
    last_err: Exception | None = None
    for endpoint in endpoints:
        try:
            from huggingface_hub import hf_hub_download

            kw = dict(kwargs)
            if endpoint:
                kw["endpoint"] = endpoint
            cached = hf_hub_download(**kw)
            dst.write_bytes(Path(cached).read_bytes())
            return
        except Exception as exc:
            last_err = exc
    if last_err:
        raise last_err


def download_many(pairs: list[tuple[str, Path]], data_root: Path | None = None) -> None:
    if not pairs:
        return
    workers = min(download_workers(), len(pairs))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda p: download_file(p[0], p[1], data_root), pairs))


def find_ref_paths(task_dir: Path, number: str, data_root: Path) -> list[str]:
    refs: list[str] = []
    i = 0
    while True:
        found = False
        for ext in IMAGE_EXTENSIONS:
            p = task_dir / f"{number}_{i}{ext}"
            if p.exists():
                refs.append(str(p.relative_to(data_root)))
                found = True
                break
        if not found:
            break
        i += 1
    return refs


def load_metadata(data_root: Path) -> list[dict]:
    meta_path = data_root / "metadata.json"
    if not meta_path.exists():
        return []
    return json.loads(meta_path.read_text(encoding="utf-8"))


def setup_subset(data_root: Path, samples_per_task: int = 2) -> list[dict]:
    data_dir = data_root / "data"
    task_types, by_task, sample_ids = build_file_index()
    subset: list[dict] = []
    for task in task_types:
        ids = sorted(sample_ids.get(task, set()))
        if samples_per_task > 0:
            ids = ids[:samples_per_task]
        if not ids:
            continue
        task_dir = data_dir / task
        task_dir.mkdir(parents=True, exist_ok=True)
        pairs: list[tuple[str, Path]] = []
        if "types.json" in by_task[task]:
            pairs.append((f"{task}/types.json", task_dir / "types.json"))
        for number in ids:
            prefix = f"{number}_"
            for name in by_task[task]:
                if name.startswith(prefix):
                    pairs.append((f"{task}/{name}", task_dir / name))
        download_many(pairs, data_root)
        types_map = {}
        types_path = task_dir / "types.json"
        if types_path.exists():
            types_map = json.loads(types_path.read_text(encoding="utf-8"))
        for number in ids:
            prompt_path = task_dir / f"{number}_prompt.txt"
            if not prompt_path.exists():
                continue
            refs = find_ref_paths(task_dir, number, data_root)
            if not refs:
                continue
            subset.append(
                {
                    "key": f"{task}_{number}",
                    "task": task,
                    "number": number,
                    "instruction": prompt_path.read_text(encoding="utf-8").strip(),
                    "reference_paths": refs,
                    "difficulty": types_map.get(number),
                }
            )
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "metadata.json").write_text(
        json.dumps(subset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return subset


def filter_metadata(
    meta: list[dict],
    task_types: list[str] | str | None = None,
    samples_per_task: int = 0,
) -> list[dict]:
    allowed = None
    if task_types:
        if isinstance(task_types, str):
            allowed = {t.strip() for t in task_types.split(",") if t.strip()}
        else:
            allowed = {t for t in task_types if t}
    counts: dict[str, int] = defaultdict(int)
    out: list[dict] = []
    for item in meta:
        task = item["task"]
        if allowed and task not in allowed:
            continue
        if samples_per_task > 0 and counts[task] >= samples_per_task:
            continue
        counts[task] += 1
        out.append(item)
    return out


def iter_samples(data_root: Path, task_types: list[str] | None = None, limit_per_task: int = 0):
    meta = load_metadata(data_root)
    allowed = set(task_types) if task_types else None
    counts: dict[str, int] = defaultdict(int)
    for item in meta:
        task = item["task"]
        if allowed and task not in allowed:
            continue
        if limit_per_task and counts[task] >= limit_per_task:
            continue
        counts[task] += 1
        yield item


def count_total(data_root: Path, task_types: list[str] | None = None) -> int:
    return sum(1 for _ in iter_samples(data_root, task_types=task_types))


def multibanana_job_totals(data_root: Path, samples_per_task: int = 2) -> tuple[int, int]:
    n = count_total(data_root)
    if n:
        return n, n
    per = samples_per_task if samples_per_task > 0 else 50
    return len(MULTIBANANA_TASK_TYPES) * per, len(MULTIBANANA_TASK_TYPES) * per


def estimate_dataset_stats(samples_per_task: int = 2) -> dict:
    """Estimate task/sample counts from HF index without downloading."""
    _, _, sample_ids = build_file_index()
    per_task = {task: len(ids) for task, ids in sample_ids.items()}
    task_count = len(per_task)
    if samples_per_task > 0:
        total = sum(min(samples_per_task, n) for n in per_task.values())
        mode = "smoke"
        label = f"每类 {samples_per_task} 条（smoke）"
    else:
        total = sum(per_task.values())
        mode = "full"
        label = "全量（每类全部样本）"
    return {
        "mode": mode,
        "label": label,
        "task_count": task_count,
        "total_samples": total,
        "per_task_max": max(per_task.values()) if per_task else 0,
        "per_task_min": min(per_task.values()) if per_task else 0,
        "per_task": per_task,
    }
