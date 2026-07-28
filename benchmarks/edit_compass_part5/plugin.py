"""Edit-Compass Part5 benchmark plugin."""

from __future__ import annotations

import json
import os
from pathlib import Path

from core.benchmark.spec import BenchmarkManifest
from core.dataset.params import resolve_samples_per_task
from core.dataset.stats import normalize_task_types
from core.paths import PROJECT_ROOT, resolve_viewer_image
from core.runner.args import runner_argv_head

from benchmarks.edit_compass_part5.data_utils import (
    METRICS,
    PART5_TASKS,
    TASK_LABELS,
    TASK_TOTALS,
    dataset_stats,
    scope_items,
)


def _scoped_items(manifest: BenchmarkManifest, params: dict) -> list[dict]:
    task_types = normalize_task_types(params.get("task_types")) or PART5_TASKS
    subset = resolve_samples_per_task(params)
    return scope_items(
        manifest.data_dir(),
        task_types=list(task_types),
        subset=subset,
        seed=int(params.get("seed", 42)),
    )


def _load_metric_rows_safe(path: Path) -> list[dict] | None:
    """Read eval metric JSON; return None if missing or mid-write (resume must not crash)."""
    if not path.is_file():
        return None
    try:
        if path.stat().st_size < 2:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    return data if isinstance(data, list) else None


def _eval_complete(part5_root: Path, task: str, save_id: str) -> bool:
    for metric in METRICS:
        path = part5_root / task / f"{task}_{metric}.json"
        rows = _load_metric_rows_safe(path)
        if rows is None:
            return False
        row = next((r for r in rows if str(r.get("save_id")) == str(save_id)), None)
        if not row or row.get(f"eval_{metric}_status") != "Success":
            return False
    return True


def measure_progress(
    manifest: BenchmarkManifest,
    output_dir: Path,
    model_path: str,
    params: dict,
) -> dict:
    items = _scoped_items(manifest, params)
    total = len(items)
    if total == 0:
        return {"gen_done": 0, "gen_total": 0, "eval_done": 0, "eval_total": 0}

    model_name = Path(model_path.rstrip("/")).name
    language = str(params.get("language", "en"))
    part5_root = output_dir / model_name / language / "Part5"

    gen_done = 0
    eval_done = 0
    for item in items:
        task = item["task"]
        save_id = str(item["save_id"])
        png = part5_root / task / f"{save_id}.png"
        if png.is_file() and png.stat().st_size > 100:
            gen_done += 1
        if _eval_complete(part5_root, task, save_id):
            eval_done += 1

    return {
        "gen_done": gen_done,
        "gen_total": total,
        "eval_done": eval_done,
        "eval_total": total,
    }


def get_console_options(manifest: BenchmarkManifest, params: dict | None = None) -> dict:
    options = []
    for task in PART5_TASKS:
        count = TASK_TOTALS.get(task, 0)
        options.append({
            "value": task,
            "label": f"{TASK_LABELS.get(task, task)} ({count})",
            "count": count,
        })
    return {"task_types": options}


def get_dataset_info(manifest: BenchmarkManifest, params: dict) -> dict:
    stats = dataset_stats(manifest.data_dir(), params)
    task_types = normalize_task_types(params.get("task_types"))
    samples = resolve_samples_per_task(params)
    return {
        "benchmark": manifest.id,
        "title": manifest.title,
        "dataset_mode": params.get("dataset_mode", "full"),
        "samples_per_task": samples if samples > 0 else None,
        "task_types": task_types or PART5_TASKS,
        "mode": "full" if samples <= 0 else "smoke",
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
    subset = resolve_samples_per_task(params)
    args.extend(["--subset", str(subset)])
    task_types = normalize_task_types(params.get("task_types"))
    if task_types:
        args.extend(["--tasks", *task_types])
    args.extend([
        "--language", str(params.get("language", "en")),
        "--seed", str(params.get("seed", 42)),
        "--num-inference-steps", str(params.get("num_inference_steps", 40)),
        "--eval-workers", str(params.get("eval_nproc", 8)),
    ])
    if params.get("gen_only"):
        args.append("--infer-only")
    if params.get("eval_only"):
        args.append("--eval-only")
    if params.get("judge_model"):
        args.extend(["--eval-model", str(params["judge_model"])])
    if params.get("full_gpu"):
        args.append("--full-gpu")
    if params.get("skip_existing"):
        args.append("--skip-existing")
    ec_root = manifest.project_root()
    if ec_root is None:
        raw = os.environ.get("EDIT_COMPASS_ROOT", "").strip()
        ec_root = Path(raw).expanduser() if raw else None
    if ec_root:
        args.extend(["--ec-root", str(ec_root)])
    return args


def build_viewer_data(
    manifest: BenchmarkManifest,
    job: dict,
    output_dir: Path,
    *,
    model_label: str = "FireRed",
) -> dict:
    from benchmarks.edit_compass_part5.export_viewer import build_payload

    params = job.get("params") or {}
    model_path = job.get("model_path") or ""
    model_folder = Path(model_path).name if model_path else model_label
    judge = job.get("judge") or {}
    archive = (job.get("public_archive_dir") or "").strip()
    return build_payload(
        manifest.data_dir(),
        output_dir,
        model_folder=model_folder,
        model_label=model_label,
        language=str(params.get("language", "en")),
        job_label=job.get("id"),
        judge_model=judge.get("judge_model"),
        dimensions=manifest.viewer_dimensions(),
        score_scale=manifest.score_scale(),
        archive_base=Path(archive) if archive else None,
    )


def resolve_image(manifest: BenchmarkManifest, path: str) -> Path | None:
    extra = [manifest.project_root()] if manifest.project_root() else None
    return resolve_viewer_image(path, data_dir=manifest.data_dir(), extra_roots=extra)
