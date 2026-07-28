"""GPU discovery via nvidia-smi."""

from __future__ import annotations

import shutil
import socket
import subprocess
import threading
import time

_CACHE_TTL_SEC = 2.0
_cache_lock = threading.Lock()
_cache: dict | None = None
_cache_at = 0.0


def list_gpus(*, force: bool = False) -> list[dict]:
    global _cache, _cache_at
    now = time.monotonic()
    with _cache_lock:
        if not force and _cache is not None and (now - _cache_at) < _CACHE_TTL_SEC:
            return list(_cache["gpus"])

    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        with _cache_lock:
            if _cache is not None:
                return list(_cache["gpus"])
        return []

    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        idx, name, mem_total, mem_used, util = parts[:5]
        gpus.append({
            "index": int(idx),
            "name": name,
            "memory_total_mb": int(float(mem_total)),
            "memory_used_mb": int(float(mem_used)),
            "utilization_pct": int(float(util)),
        })

    with _cache_lock:
        _cache = {"gpus": gpus}
        _cache_at = now
    return gpus


def gpu_summary() -> dict:
    gpus = list_gpus()
    return {"count": len(gpus), "gpus": gpus, "hostname": socket.gethostname()}
