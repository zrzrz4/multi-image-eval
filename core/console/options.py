"""Console dynamic options — dispatches to benchmark plugins."""

from __future__ import annotations

from core.benchmark.loader import load_manifest, load_plugin_module
from core.judge.config import get_judge_config_public
from core.paths import PROJECT_ROOT


def _judge_model_options() -> list[dict]:
    cfg = get_judge_config_public(PROJECT_ROOT)
    default = cfg.get("model") or "gemini-3-flash-preview"
    return [
        {"value": "", "label": f"全局默认 ({default})"},
        {"value": default, "label": default},
    ]


def get_benchmark_options(benchmark_id: str, params: dict | None = None) -> dict:
    manifest = load_manifest(benchmark_id)
    plugin = load_plugin_module(benchmark_id)
    out: dict = {"judge_models": _judge_model_options()}
    if hasattr(plugin, "get_console_options"):
        out.update(plugin.get_console_options(manifest, params or {}))
    return out
