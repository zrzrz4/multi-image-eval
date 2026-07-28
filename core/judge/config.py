"""Read/write global judge gateway config in project .env."""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

JUDGE_KEYS = ("GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI_MODEL")


def env_path(project_root: str | Path) -> Path:
    return Path(project_root) / ".env"


def load_dotenv_map(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def apply_gemini_to_environ(values: dict[str, str]) -> None:
    for k in JUDGE_KEYS:
        if k in values and values[k] is not None:
            os.environ[k] = str(values[k])


def reload_gemini_from_dotenv(project_root: str | Path) -> dict[str, str]:
    path = env_path(project_root)
    data = load_dotenv_map(path)
    subset = {k: data[k] for k in JUDGE_KEYS if k in data}
    apply_gemini_to_environ(subset)
    return {
        "api_key": os.environ.get("GEMINI_API_KEY", ""),
        "base_url": os.environ.get("GEMINI_BASE_URL", ""),
        "model": os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview"),
    }


def mask_api_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:3] + "*" * max(4, len(key) - 7) + key[-4:]


def get_judge_config_public(project_root: str | Path) -> dict:
    reload_gemini_from_dotenv(project_root)
    key = os.environ.get("GEMINI_API_KEY", "")
    return {
        "api_key_configured": bool(key and key not in ("your_key_here", "changeme", "REPLACE_ME")),
        "api_key_masked": mask_api_key(key) if key else "",
        "base_url": os.environ.get("GEMINI_BASE_URL", ""),
        "model": os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview"),
        "env_path": str(env_path(project_root)),
    }


def _set_kv_lines(lines: list[str], key: str, value: str) -> list[str]:
    out: list[str] = []
    seen = False
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith(f"{key}=") or (
            stripped.startswith(key) and "=" in stripped and stripped.split("=", 1)[0] == key
        ):
            out.append(f"{key}={value}\n")
            seen = True
        else:
            out.append(raw if raw.endswith("\n") else raw + "\n")
    if not seen:
        out.append(f"{key}={value}\n")
    return out


def write_judge_config(
    project_root: str | Path,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    path = env_path(project_root)
    if not path.is_file():
        raise FileNotFoundError(f"找不到 .env: {path}")

    updates: dict[str, str] = {}
    if api_key is not None:
        key = api_key.strip()
        if key:
            if key in ("your_key_here", "changeme", "REPLACE_ME"):
                raise ValueError("API Key 无效")
            updates["GEMINI_API_KEY"] = key
    if base_url is not None:
        url = base_url.strip().rstrip("/")
        if not url:
            raise ValueError("Base URL 不能为空")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("Base URL 须以 http:// 或 https:// 开头")
        updates["GEMINI_BASE_URL"] = url
    if model is not None:
        mid = model.strip()
        if not mid:
            raise ValueError("模型名不能为空")
        updates["GEMINI_MODEL"] = mid

    if not updates:
        raise ValueError("没有可保存的改动")

    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for k, v in updates.items():
        lines = _set_kv_lines(lines, k, v)

    directory = path.parent
    fd, tmp = tempfile.mkstemp(prefix=".env.", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass

    apply_gemini_to_environ({k: updates[k] for k in updates})
    return get_judge_config_public(project_root)


def list_models_from_gateway(base_url: str | None = None, api_key: str | None = None) -> list[str]:
    base = (base_url or os.environ.get("GEMINI_BASE_URL") or "").rstrip("/")
    key = api_key or os.environ.get("GEMINI_API_KEY") or ""
    if not base or not key:
        raise ValueError("需要有效的 Base URL 与 API Key 才能列模型")
    url = base + "/models"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"列模型失败 HTTP {e.code}: {body}") from e
    except Exception as e:
        raise RuntimeError(f"列模型失败: {e}") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError("列模型返回不是合法 JSON") from e

    ids: list[str] = []
    items = []
    if isinstance(data, dict):
        items = data.get("data") or data.get("models") or []
    elif isinstance(data, list):
        items = data
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                mid = it.get("id") or it.get("name") or it.get("model")
                if mid:
                    ids.append(re.sub(r"^models/", "", str(mid)))
            elif isinstance(it, str):
                ids.append(it)

    seen, uniq = set(), []
    for x in ids:
        x = x.strip()
        if x and x not in seen:
            seen.add(x)
            uniq.append(x)
    if not uniq:
        raise RuntimeError("网关未返回可用模型")
    return uniq[:120]
