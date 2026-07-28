"""MultiBanana benchmark plugin — CLI args, dataset info, image resolution."""

from __future__ import annotations

import json
from pathlib import Path

from core.benchmark.spec import BenchmarkManifest
from core.dataset.params import resolve_samples_per_task
from core.dataset.stats import compute_subset_stats, normalize_task_types
from core.paths import PROJECT_ROOT, rel_to_viewer_path, resolve_viewer_image
from core.runner.args import (
    append_dataset_flags,
    append_eval_flags,
    append_inference_flags,
    runner_argv_head,
)

from benchmarks.multibanana.data_utils import MULTIBANANA_TASK_LABELS, filter_metadata, load_metadata


def _load_items(data_root: Path) -> list[dict]:
    return load_metadata(data_root)


def get_console_options(manifest: BenchmarkManifest, params: dict | None = None) -> dict:
    data_root = manifest.data_dir()
    items = _load_items(data_root)
    if not items:
        return {"task_types": []}
    per_task = {}
    for item in items:
        per_task[item["task"]] = per_task.get(item["task"], 0) + 1
    options = []
    for task in sorted(per_task.keys()):
        label = MULTIBANANA_TASK_LABELS.get(task, task)
        options.append({
            "value": task,
            "label": f"{label} ({per_task[task]})",
            "count": per_task[task],
        })
    return {"task_types": options}


def get_dataset_info(manifest: BenchmarkManifest, params: dict) -> dict:
    samples = resolve_samples_per_task(params)
    task_types = normalize_task_types(params.get("task_types"))
    data_root = manifest.data_dir()
    items = _load_items(data_root)

    if items:
        stats = compute_subset_stats(
            items,
            task_types=task_types,
            samples_per_task=samples,
        )
        stats["source"] = "local_metadata"
        stats["metadata_total"] = len(items)
        return {
            "benchmark": manifest.id,
            "title": manifest.title,
            "dataset_mode": params.get("dataset_mode", "smoke"),
            "samples_per_task": samples if samples > 0 else None,
            "task_types": task_types,
            **stats,
        }

    try:
        from benchmarks.multibanana.data_utils import estimate_dataset_stats

        stats = estimate_dataset_stats(samples)
        stats["source"] = "hf_index"
        if task_types:
            per = stats.get("per_task") or {}
            stats["task_count"] = len([t for t in task_types if t in per])
            stats["total_samples"] = sum(
                min(samples, per[t]) if samples > 0 else per.get(t, 0)
                for t in task_types
                if t in per
            )
            stats["label"] = f"已选 {stats['task_count']} 类（预估）"
    except Exception as exc:
        task_count = len(task_types) if task_types else 36
        per = samples if samples > 0 else 30
        total = task_count * per
        stats = {
            "mode": "full" if samples <= 0 else "smoke",
            "label": "全量（预估）" if samples <= 0 else f"每类 {samples} 条（预估）",
            "task_count": task_count,
            "total_samples": total,
            "per_task_max": None,
            "per_task_min": None,
            "source": "estimate",
            "warning": str(exc),
        }

    return {
        "benchmark": manifest.id,
        "title": manifest.title,
        "dataset_mode": params.get("dataset_mode", "smoke"),
        "samples_per_task": samples if samples > 0 else None,
        "task_types": task_types,
        **stats,
    }


def build_run_args(
    manifest: BenchmarkManifest,
    output_dir: Path,
    model_path: str,
    params: dict,
    py_bin: str,
) -> list[str]:
    args = runner_argv_head(manifest, output_dir, model_path, py_bin)
    append_dataset_flags(args, params)
    append_inference_flags(args, params)
    append_eval_flags(args, params)
    return args


def _scoped_items(manifest: BenchmarkManifest, params: dict) -> list[dict]:
    items = _load_items(manifest.data_dir())
    if not items:
        return []
    samples = resolve_samples_per_task(params)
    per_task_limit = samples if samples > 0 else 0
    task_types = normalize_task_types(params.get("task_types"))
    return filter_metadata(items, task_types or None, per_task_limit)


def measure_progress(
    manifest: BenchmarkManifest,
    output_dir: Path,
    model_path: str,
    params: dict,
) -> dict:
    """Count generated images and judge files on disk (resume / API progress)."""
    items = _scoped_items(manifest, params)
    total = len(items)
    if total == 0:
        return {"gen_done": 0, "gen_total": 0, "eval_done": 0, "eval_total": 0}

    min_bytes = 1024
    judge_dir = output_dir / "judge"
    gen_done = 0
    eval_done = 0
    for item in items:
        gen_path = output_dir / f"{item['key']}.jpg"
        if gen_path.is_file() and gen_path.stat().st_size >= min_bytes:
            gen_done += 1
        judge_file = judge_dir / f"{item['key']}_gemini_judge.txt"
        if judge_file.is_file():
            try:
                from benchmarks.multibanana.gemini_judge import extract_scores

                if extract_scores(judge_file.read_text(encoding="utf-8")):
                    eval_done += 1
            except OSError:
                pass

    return {
        "gen_done": gen_done,
        "gen_total": total,
        "eval_done": eval_done,
        "eval_total": total,
    }


def build_viewer_data(
    manifest: BenchmarkManifest,
    job: dict,
    output_dir: Path,
    *,
    model_label: str = "FireRed",
) -> dict:
    from benchmarks.multibanana.export_viewer import build_payload

    judge = job.get("judge") or {}
    archive = (job.get("public_archive_dir") or "").strip()
    scoped = _scoped_items(manifest, job.get("params") or {})
    return build_payload(
        manifest.data_dir(),
        output_dir,
        model_label=model_label,
        job_label=job.get("id"),
        judge_model=judge.get("judge_model"),
        dimensions=manifest.viewer_dimensions(),
        score_scale=manifest.score_scale(),
        archive_base=Path(archive) if archive else None,
        scope_meta=scoped,
    )


def resolve_image(manifest: BenchmarkManifest, path: str) -> Path | None:
    extra = [manifest.project_root()] if manifest.project_root() else None
    return resolve_viewer_image(path, data_dir=manifest.data_dir(), extra_roots=extra)
