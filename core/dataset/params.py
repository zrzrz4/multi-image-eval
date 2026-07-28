"""Shared dataset parameter helpers."""

from __future__ import annotations


def resolve_samples_per_task(params: dict) -> int:
    if params.get("dataset_mode") == "full":
        return 0
    return max(1, int(params.get("samples_per_task", 2)))
