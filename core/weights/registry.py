"""Register and persist custom model weights."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from core.paths import CONFIG_DIR, PROJECT_ROOT

CUSTOM_WEIGHTS_FILE = CONFIG_DIR / "custom_weights.json"
UPLOADS_DIR = PROJECT_ROOT / "uploads" / "weights"


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", (text or "weight").strip()).strip("-").lower()
    return s[:48] or "weight"


def _load_custom() -> list[dict]:
    if not CUSTOM_WEIGHTS_FILE.exists():
        return []
    data = json.loads(CUSTOM_WEIGHTS_FILE.read_text(encoding="utf-8"))
    return list(data.get("weights") or [])


def _save_custom(weights: list[dict]) -> None:
    CUSTOM_WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_WEIGHTS_FILE.write_text(
        json.dumps({"weights": weights}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_weight_upload(filename: str, src_path: Path) -> Path:
    """Copy uploaded file into uploads/weights and return final path."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix or ".safetensors"
    dest_dir = UPLOADS_DIR / f"{_slug(Path(filename).stem)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"weight{ext}"
    shutil.copy2(src_path, dest)
    return dest.resolve()


def register_weight(
    *,
    model_id: str,
    label: str,
    path: str,
    weight_id: str | None = None,
    source: str = "path",
) -> dict:
    label = (label or "").strip()
    path = (path or "").strip()
    if not label:
        raise ValueError("权重名称不能为空")
    if not path:
        raise ValueError("权重路径不能为空")
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise ValueError(f"路径不存在: {path}")

    wid = weight_id or f"custom-{_slug(label)}"
    base = wid
    existing = {w["id"] for w in _load_custom()}
    n = 2
    while wid in existing:
        wid = f"{base}-{n}"
        n += 1

    entry = {
        "id": wid,
        "model_id": model_id,
        "label": label,
        "path": str(resolved),
        "source": source,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    weights = _load_custom()
    weights.append(entry)
    _save_custom(weights)
    return {**entry, "available": True}


def custom_weights_for_model(model_id: str) -> list[dict]:
    return [w for w in _load_custom() if w.get("model_id") == model_id]
