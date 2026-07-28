"""Dataset scope info — dispatches to benchmark plugins."""

from __future__ import annotations

from core.benchmark.loader import load_manifest, load_plugin_module
from core.registry import load_benchmark


def get_dataset_info(benchmark_id: str, params: dict | None = None) -> dict:
    params = dict(params or {})
    manifest = load_manifest(benchmark_id)
    plugin = load_plugin_module(benchmark_id)
    if hasattr(plugin, "get_dataset_info"):
        return plugin.get_dataset_info(manifest, params)
    bench = load_benchmark(benchmark_id)
    return {
        "benchmark": benchmark_id,
        "title": bench["title"],
        "dataset_mode": params.get("dataset_mode", "smoke"),
        "total_samples": None,
    }
