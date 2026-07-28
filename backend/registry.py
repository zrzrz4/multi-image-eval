"""Backward-compatible re-exports. Prefer `core.registry`."""

from core.registry import (  # noqa: F401
    list_viewer_benchmarks,
    load_benchmark,
    load_benchmark_manifest,
    load_model,
    load_models,
    load_weight,
)
