"""Discover and load benchmark plugins."""

from __future__ import annotations

import importlib
from pathlib import Path

from core.benchmark.spec import BenchmarkManifest
from core.paths import BENCHMARKS_DIR


def discover_benchmark_ids() -> list[str]:
    ids = []
    if not BENCHMARKS_DIR.exists():
        return ids
    for child in sorted(BENCHMARKS_DIR.iterdir()):
        if child.is_dir() and (child / "manifest.json").exists():
            ids.append(child.name)
    return ids


def load_manifest(benchmark_id: str) -> BenchmarkManifest:
    return BenchmarkManifest.load(benchmark_id)


def load_all_manifests() -> list[BenchmarkManifest]:
    return [load_manifest(bid) for bid in discover_benchmark_ids()]


def load_plugin_module(benchmark_id: str):
    return importlib.import_module(f"benchmarks.{benchmark_id}.plugin")
