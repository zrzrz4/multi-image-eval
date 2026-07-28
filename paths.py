"""Backward-compatible path exports. Prefer `core.paths`."""

from __future__ import annotations

import os

from core.paths import (  # noqa: F401
    BENCHMARKS_DIR,
    CONFIG_DIR,
    DATA_DIR,
    FRONTEND_DIR,
    JOBS_DIR,
    LOGS_DIR,
    OUTPUTS_DIR,
    PROJECT_ROOT,
    VIEWER_DATA_DIR,
    benchmark_data_dir,
    benchmark_outputs_dir,
)

MODEL_DEFAULT = os.environ.get("FIRERED_MODEL_PATH", "")
MULTIBANANA_DATA = benchmark_data_dir("multibanana")
MULTIBANANA_OUTPUTS = benchmark_outputs_dir("multibanana")
