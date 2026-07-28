"""Normalize benchmark viewer payloads to a stable console schema."""

from __future__ import annotations

from typing import Any

from core.benchmark.spec import BenchmarkManifest


def _alias_item(item: dict) -> dict:
    out = dict(item)
    if "model_output" not in out and out.get("firered"):
        out["model_output"] = out["firered"]
    if "model_scores" not in out and out.get("firered_scores"):
        out["model_scores"] = out["firered_scores"]
    if "model_label" not in out and out.get("firered_label"):
        out["model_label"] = out["firered_label"]
    return out


def normalize_viewer_payload(payload: dict, manifest: BenchmarkManifest) -> dict:
    """Add manifest-driven dimensions/score_scale and stable field aliases."""
    viewer = manifest.viewer or {}
    dimensions = viewer.get("dimensions") or payload.get("dimensions") or []
    score_scale = viewer.get("score_scale") or payload.get("score_scale") or 10

    items = [_alias_item(i) for i in (payload.get("items") or [])]
    raw_samples = payload.get("samples")
    if raw_samples is None:
        samples = items
    else:
        samples = [_alias_item(i) for i in raw_samples]

    model_avg = payload.get("model_avg_score")
    if model_avg is None:
        model_avg = payload.get("firered_avg_score")

    return {
        **payload,
        "benchmark_id": manifest.id,
        "dimensions": dimensions,
        "score_scale": score_scale,
        "model_avg_score": model_avg,
        "firered_avg_score": model_avg,
        "items": items,
        "samples": samples,
        "gallery": {
            "per_task_all": viewer.get("samples_per_task_all", 3),
            "per_task_filtered": viewer.get("samples_per_task_filtered", 6),
        },
    }
