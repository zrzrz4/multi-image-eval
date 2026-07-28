"""Merge global judge defaults with per-job overrides."""

from __future__ import annotations

import os
from typing import Any

from core.judge.config import reload_gemini_from_dotenv
from core.paths import PROJECT_ROOT

_PLACEHOLDER_URLS = {"", "http://localhost", "https://localhost"}


def effective_judge_params(job_params: dict | None = None) -> dict[str, Any]:
    """Return resolved judge settings for a job (global .env + per-job overrides)."""
    reload_gemini_from_dotenv(PROJECT_ROOT)
    params = dict(job_params or {})
    out = {
        "judge_model": os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview"),
        "base_url": os.environ.get("GEMINI_BASE_URL", ""),
        "temperature": float(params.get("judge_temperature", 0.1)),
        "max_tokens": int(params.get("judge_max_tokens", 8192)),
    }
    if params.get("judge_model"):
        out["judge_model"] = str(params["judge_model"]).strip()
    if params.get("judge_base_url"):
        url = str(params["judge_base_url"]).strip().rstrip("/")
        if url and url not in _PLACEHOLDER_URLS:
            out["base_url"] = url
    return out


def apply_judge_env(env: dict[str, str], job_params: dict | None = None) -> dict[str, str]:
    """Inject effective judge settings into subprocess environment."""
    effective = effective_judge_params(job_params)
    if effective["judge_model"]:
        env["GEMINI_MODEL"] = effective["judge_model"]
        env["BENCHMARK_JUDGE_MODEL"] = effective["judge_model"]
    if effective["base_url"]:
        env["GEMINI_BASE_URL"] = effective["base_url"]
        env["OPENAI_BASE_URL"] = effective["base_url"]
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        env["OPENAI_API_KEY"] = key
    return env
