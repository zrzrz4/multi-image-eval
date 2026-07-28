"""Helpers to build benchmark runner CLI argv from manifest + params."""

from __future__ import annotations

from pathlib import Path

from core.benchmark.spec import BenchmarkManifest
from core.dataset.params import resolve_samples_per_task
from core.dataset.stats import normalize_task_types


def runner_argv_head(
    manifest: BenchmarkManifest,
    output_dir: Path,
    model_path: str,
    py_bin: str,
    *,
    progress_shard: int | None = None,
) -> list[str]:
    """Common argv prefix: python, script, roots, progress file."""
    return [
        py_bin,
        str(manifest.runner_script()),
        "--data-root", str(manifest.data_dir()),
        "--output-dir", str(output_dir),
        "--model-path", model_path,
        "--progress-file", str(manifest.progress_file(output_dir, progress_shard)),
    ]


def append_dataset_flags(args: list[str], params: dict) -> list[str]:
    samples = resolve_samples_per_task(params)
    args.extend(["--samples-per-task", str(samples)])
    task_types = normalize_task_types(params.get("task_types"))
    if task_types:
        args.extend(["--task-types", ",".join(task_types)])
    if params.get("setup_data"):
        args.append("--setup-data")
    if params.get("dataset_mode") == "full" or samples <= 0:
        if params.get("setup_data"):
            args.append("--force-setup")
    return args


def append_inference_flags(args: list[str], params: dict, defaults: dict | None = None) -> list[str]:
    d = defaults or {}
    args.extend([
        "--num-inference-steps", str(params.get("num_inference_steps", d.get("num_inference_steps", 50))),
        "--seed", str(params.get("seed", d.get("seed", 49))),
        "--true-cfg-scale", str(params.get("true_cfg_scale", d.get("true_cfg_scale", 4.0))),
    ])
    return args


def append_eval_flags(args: list[str], params: dict, defaults: dict | None = None) -> list[str]:
    d = defaults or {}
    args.extend(["--eval-nproc", str(params.get("eval_nproc", d.get("eval_nproc", 8)))])
    if params.get("gen_only"):
        args.append("--gen-only")
    if params.get("eval_only"):
        args.append("--eval-only")
    if not params.get("eval_inline", True):
        args.append("--no-eval-inline")
    if params.get("judge_model"):
        args.extend(["--judge-model", str(params["judge_model"])])
    return args
