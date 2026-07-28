"""Model registry and benchmark discovery."""

from __future__ import annotations

import json
from pathlib import Path

from core.benchmark.loader import load_all_manifests, load_manifest
from core.paths import CONFIG_DIR
from core.weights.registry import custom_weights_for_model


def _models_config() -> dict:
    path = CONFIG_DIR / "models.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if "models" in data:
        return data
    return {"models": [{"id": "default", "label": "Default", "weights": data}]}


def load_models() -> list[dict]:
    out = []
    for model in _models_config()["models"]:
        weights = []
        seen_ids = set()
        for w in model.get("weights", []):
            entry = {
                **w,
                "available": Path(w["path"]).exists(),
                "model_id": model["id"],
                "model_label": model["label"],
                "builtin": True,
            }
            weights.append(entry)
            seen_ids.add(w["id"])
        for w in custom_weights_for_model(model["id"]):
            if w["id"] in seen_ids:
                continue
            weights.append({
                **w,
                "available": Path(w["path"]).exists(),
                "model_id": model["id"],
                "model_label": model["label"],
                "builtin": False,
            })
            seen_ids.add(w["id"])
        out.append({**model, "weights": weights})
    return out


def load_model(model_id: str) -> dict:
    for model in load_models():
        if model["id"] == model_id:
            return model
    raise KeyError(model_id)


def load_weight(model_id: str, weight_id: str) -> dict:
    model = load_model(model_id)
    for w in model["weights"]:
        if w["id"] == weight_id:
            return w
    raise KeyError(weight_id)


def load_benchmark(id_: str | None = None) -> dict | list[dict]:
    if id_ is None:
        return [m.to_console_dict() for m in load_all_manifests()]
    return load_manifest(id_).to_console_dict()


def load_benchmark_manifest(id_: str):
    return load_manifest(id_)


def list_viewer_benchmarks() -> list[dict]:
    out = []
    for manifest in load_all_manifests():
        viewer = manifest.viewer or {}
        if not viewer.get("enabled", True):
            continue
        out.append({
            "id": manifest.id,
            "title": viewer.get("title", manifest.title),
            "data_file": manifest.viewer_data_file(),
        })
    return out
