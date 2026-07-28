"""Group historical jobs into parameter sets and test versions (rededit-style)."""

from __future__ import annotations

import json
from pathlib import Path

from core.benchmark.loader import load_manifest
from core.jobs.manager import list_jobs
from core.paths import resolve_job_output_dir


def _param_value(job: dict, key: str):
    params = job.get("params") or {}
    judge = job.get("judge") or {}
    if key in params:
        val = params[key]
        if key == "task_types" and isinstance(val, list):
            return sorted(str(t) for t in val)
        return val
    if key == "judge_model":
        return judge.get("judge_model") or params.get("judge_model") or ""
    return params.get(key)


def params_key_from_job(job: dict) -> str:
    """Fingerprint inference + dataset + judge settings for grouping."""
    try:
        manifest = load_manifest(job["benchmark"])
        keys = manifest.fingerprint_param_keys()
    except KeyError:
        keys = list((job.get("params") or {}).keys())

    payload = {
        "weight": job.get("weight_id") or job.get("weight_label") or "",
    }
    for key in keys:
        if key == "weight":
            continue
        payload[key] = _param_value(job, key)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def params_summary_from_job(job: dict) -> str:
    params = job.get("params") or {}
    judge = job.get("judge") or {}
    try:
        manifest = load_manifest(job["benchmark"])
        scale = manifest.score_scale()
    except KeyError:
        scale = 10

    parts = []
    mode = params.get("dataset_mode")
    if mode:
        if mode == "full":
            parts.append("全量")
        else:
            parts.append(f"smoke·{params.get('samples_per_task', 2)}条/类")
    task_types = params.get("task_types") or []
    if task_types:
        if len(task_types) <= 4:
            parts.append("、".join(task_types))
        else:
            parts.append(f"{len(task_types)}类")
    elif mode:
        parts.append("全部类")

    for key, label in (
        ("num_inference_steps", "steps"),
        ("seed", "seed"),
        ("true_cfg_scale", "CFG"),
    ):
        if key in params:
            parts.append(f"{label} {params[key]}")

    judge_model = params.get("judge_model") or judge.get("judge_model") or ""
    parts.append(str(judge_model) if judge_model else "全局裁判")

    summary = " · ".join(parts) if parts else "默认参数"
    _ = scale  # reserved for future per-benchmark summary templates
    return summary


def _job_score(job: dict) -> float | None:
    try:
        manifest = load_manifest(job["benchmark"])
        eval_path = manifest.eval_summary_path(resolve_job_output_dir(job))
        if not eval_path.exists():
            return None
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        return data.get("avg_score")
    except (KeyError, json.JSONDecodeError, OSError):
        return None


def _progress_label(job: dict) -> str:
    status = job.get("status", "")
    prog = job.get("progress") or {}
    if status == "running":
        phase = prog.get("phase") or "running"
        if phase == "loading_model":
            return "模型预热加载中（约3～8分钟）"
        if phase == "generating":
            gen_done = prog.get("gen_done", 0)
            if gen_done < 1:
                return "模型预热加载中（约3～8分钟）"
            return f"生成 {gen_done}/{prog.get('gen_total', 0)}"
        if phase == "pipeline":
            return (
                f"流水线 生成 {prog.get('gen_done', 0)}/{prog.get('gen_total', 0)}"
                f" · 评测 {prog.get('eval_done', 0)}/{prog.get('eval_total', 0)}"
            )
        if phase == "evaluating":
            return f"评测 {prog.get('eval_done', 0)}/{prog.get('eval_total', 0)}"
        return phase
    if status == "completed":
        score = _job_score(job)
        if score is not None:
            try:
                scale = load_manifest(job["benchmark"]).score_scale()
            except KeyError:
                scale = 10
            return f"均分 {score}/{scale}"
        return "已完成"
    if status == "failed":
        return "失败"
    if status == "cancelled":
        return "已取消"
    return status or "—"


def _version_item(job: dict, index: int) -> dict:
    from core.jobs.control import job_can_delete, job_can_resume

    return {
        "id": job["id"],
        "label": f"第{index + 1}次测试",
        "version_index": index + 1,
        "status": job.get("status"),
        "created_at": job.get("created_at"),
        "progress": job.get("progress"),
        "progress_label": _progress_label(job),
        "avg_score": _job_score(job),
        "gpus": job.get("gpus") or [],
        "can_resume": job_can_resume(job),
        "can_delete": job_can_delete(job),
        "message": job.get("message"),
        "source_host": job.get("source_host"),
        "read_only": bool(job.get("read_only")),
    }


def group_jobs(jobs: list[dict]) -> list[dict]:
    """Group jobs by params fingerprint; each group sorted by created_at."""
    buckets: dict[str, list[dict]] = {}
    for job in jobs:
        key = params_key_from_job(job)
        buckets.setdefault(key, []).append(job)

    groups = []
    for key, items in buckets.items():
        items.sort(key=lambda j: j.get("created_at") or "")
        groups.append({
            "params_key": key,
            "params_summary": params_summary_from_job(items[-1]),
            "items": [_version_item(job, i) for i, job in enumerate(items)],
        })
    groups.sort(key=lambda g: g["items"][-1].get("created_at") or "")
    return groups


def list_benchmark_versions(
    *,
    model_id: str,
    weight_id: str,
    benchmark: str,
    limit: int = 100,
) -> dict:
    jobs = [
        j for j in list_jobs(limit=limit)
        if j.get("model_id") == model_id
        and j.get("weight_id") == weight_id
        and j.get("benchmark") == benchmark
    ]
    jobs.sort(key=lambda j: j.get("created_at") or "")
    groups = group_jobs(jobs)
    return {
        "model_id": model_id,
        "weight_id": weight_id,
        "benchmark": benchmark,
        "groups": groups,
        "total_runs": len(jobs),
        "group_count": len(groups),
    }
