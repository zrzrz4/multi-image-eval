"""Environment and Python runtime helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from core.paths import PROJECT_ROOT


def apply_dotenv() -> dict[str, str]:
    """Load .env into os.environ (no overwrite). Call before HF imports."""
    values = load_dotenv()
    for k, v in values.items():
        os.environ.setdefault(k, v)
    return values


def load_dotenv() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}
    return parse_env_file(env_path)


def parse_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def rededit_root_from_gen_python(gen_python: str) -> Path | None:
    py = Path(gen_python).expanduser()
    # venv/bin/python may symlink to /usr/bin/python3.12 — do not resolve().
    if py.parent.name != "bin" or py.parent.parent.name != "venv":
        return None
    root = py.parent.parent.parent
    return root if root.is_dir() else None


def discover_python_include(rededit_root: Path) -> Path | None:
    bundled = (
        rededit_root
        / ".local"
        / "python312-devel"
        / "root"
        / "usr"
        / "include"
        / "python3.12"
        / "Python.h"
    )
    if bundled.is_file():
        return bundled.parent
    return None


def _prepend_path(existing: str, entry: str) -> str:
    if not existing:
        return entry
    parts = [p for p in existing.split(os.pathsep) if p and p != entry]
    return os.pathsep.join([entry, *parts])


def inject_gen_compile_env(env: dict[str, str]) -> None:
    """Propagate RedEdit compile headers (CPATH) into job subprocesses.

    Multi-image-eval may live on CPFS while RedEdit stays at ~/work/benchmark/...
    Jobs only used to read the console .env, so ARM64 Triton builds missed Python.h
    even when install_rededit.sh had already written CPATH into RedEdit/.env.
    """
    gen_python = (
        env.get("MULTI_IMAGE_EVAL_PYTHON", "").strip()
        or load_dotenv().get("MULTI_IMAGE_EVAL_PYTHON", "").strip()
    )
    if not gen_python:
        return

    rededit_root = rededit_root_from_gen_python(gen_python)
    if rededit_root is None:
        rededit_env_path = env.get("REDEDIT_ROOT", "").strip()
        if rededit_env_path:
            rededit_root = Path(rededit_env_path).expanduser()
        else:
            return

    for key, value in parse_env_file(rededit_root / ".env").items():
        if key in {"CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "REDEDIT_ROOT"}:
            env.setdefault(key, value)

    include_dir = discover_python_include(rededit_root)
    if include_dir is None:
        return
    include = str(include_dir)
    for key in ("CPATH", "C_INCLUDE_PATH"):
        env[key] = _prepend_path(env.get(key, ""), include)


def runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env["MULTI_IMAGE_EVAL_ROOT"] = str(PROJECT_ROOT)
    for k, v in load_dotenv().items():
        env.setdefault(k, v)
    inject_gen_compile_env(env)
    return env


def python_bin() -> str:
    custom = os.environ.get("MULTI_IMAGE_EVAL_PYTHON")
    if custom and Path(custom).exists():
        return custom
    dotenv = load_dotenv()
    if dotenv.get("MULTI_IMAGE_EVAL_PYTHON") and Path(dotenv["MULTI_IMAGE_EVAL_PYTHON"]).exists():
        return dotenv["MULTI_IMAGE_EVAL_PYTHON"]
    venv_py = PROJECT_ROOT / ".venvs" / "gen" / "bin" / "python"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable
