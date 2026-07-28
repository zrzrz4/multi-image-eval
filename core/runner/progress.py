"""Shared job progress tracking for benchmark runners."""

from __future__ import annotations

import json
import threading
from pathlib import Path


def write_progress(path: str | Path | None, payload: dict) -> None:
    if not path:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class JobProgress:
    def __init__(self, gen_total: int, eval_total: int, *, pipeline: bool = False):
        self.gen_total = max(0, int(gen_total))
        self.eval_total = max(1, int(eval_total))
        self.gen_done = 0
        self.eval_done = 0
        self.phase = "generating"
        self.message = ""
        self.pipeline = pipeline
        self._lock = threading.Lock()

    def snapshot(self) -> dict:
        return {
            "phase": self.phase,
            "gen_done": self.gen_done,
            "gen_total": self.gen_total,
            "eval_done": self.eval_done,
            "eval_total": self.eval_total,
            "message": self.message,
        }

    def write(self, path: str | Path | None) -> None:
        with self._lock:
            payload = self.snapshot()
        write_progress(path, payload)

    def _sync_phase(self) -> None:
        if self.gen_done >= self.gen_total and self.eval_done >= self.eval_total:
            self.phase = "done"
        elif self.gen_done >= self.gen_total and self.eval_done < self.eval_total:
            self.phase = "evaluating"
        elif self.pipeline and self.gen_done < self.gen_total:
            self.phase = "pipeline"
        elif self.gen_done < self.gen_total:
            self.phase = "generating"
        else:
            self.phase = "evaluating"

    def set_phase(self, phase: str, path: str | Path | None = None, message: str = "") -> None:
        with self._lock:
            self.phase = phase
            if message:
                self.message = message
        if path:
            self.write(path)

    def bump_gen(self, path: str | Path | None = None, message: str = "") -> None:
        with self._lock:
            self.gen_done += 1
            if message:
                self.message = message
            self._sync_phase()
        if path:
            self.write(path)

    def bump_eval(self, path: str | Path | None = None, message: str = "") -> None:
        with self._lock:
            self.eval_done += 1
            if message:
                self.message = message
            self._sync_phase()
        if path:
            self.write(path)


def shard_items(meta: list[dict], shard_index: int, num_shards: int) -> list[dict]:
    if num_shards <= 1:
        return meta
    return [item for i, item in enumerate(meta) if i % num_shards == shard_index]
