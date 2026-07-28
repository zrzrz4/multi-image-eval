"""Benchmark manifest schema and helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.paths import BENCHMARKS_DIR, PROJECT_ROOT


@dataclass
class BenchmarkManifest:
    id: str
    title: str
    description: str = ""
    intro: str = ""
    eval_mode: str = ""
    viewer: dict[str, Any] = field(default_factory=dict)
    paths: dict[str, str] = field(default_factory=dict)
    runner: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    param_groups: dict[str, str] = field(default_factory=dict)
    params: list[dict[str, Any]] = field(default_factory=list)
    fingerprint: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, benchmark_id: str) -> BenchmarkManifest:
        path = BENCHMARKS_DIR / benchmark_id / "manifest.json"
        if not path.exists():
            raise KeyError(f"Benchmark manifest not found: {benchmark_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["id"] = benchmark_id
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})

    @property
    def data_subdir(self) -> str:
        return self.paths.get("data_subdir", self.id)

    @property
    def output_subdir(self) -> str:
        return self.paths.get("output_subdir", self.id)

    def data_dir(self) -> Path:
        root = self.paths.get("data_root")
        if root:
            return Path(root).expanduser().resolve()
        return PROJECT_ROOT / "data" / self.data_subdir

    def project_root(self) -> Path | None:
        root = self.paths.get("project_root")
        return Path(root).expanduser().resolve() if root else None

    def runner_python(self) -> Path | None:
        rel = self.runner.get("python")
        return Path(rel).expanduser().resolve() if rel else None

    def gpu_mode(self) -> str:
        return self.runner.get("gpu_mode", "shard")

    def outputs_dir(self) -> Path:
        return PROJECT_ROOT / "outputs" / self.output_subdir

    def runner_script(self) -> Path:
        rel = self.runner.get("script") or f"benchmarks/{self.id}/run.py"
        return PROJECT_ROOT / rel

    def script_path(self, key: str) -> Path | None:
        rel = self.scripts.get(key)
        return PROJECT_ROOT / rel if rel else None

    def progress_file(self, output_dir: Path, shard: int | None = None) -> Path:
        if shard is not None:
            pattern = self.artifacts.get("progress_shard_pattern", "progress_shard{shard}.json")
            return output_dir / pattern.format(shard=shard)
        return output_dir / self.artifacts.get("progress_file", "progress.json")

    def eval_summary_path(self, output_dir: Path) -> Path:
        return output_dir / self.artifacts.get("eval_summary", "eval_summary.json")

    def viewer_data_file(self) -> str:
        return self.viewer.get("data_file", f"{self.id}.json")

    def score_scale(self) -> int | float:
        return self.viewer.get("score_scale", 10)

    def viewer_dimensions(self) -> list[dict[str, str]]:
        return list(self.viewer.get("dimensions") or [])

    def sample_gallery_limits(self) -> tuple[int, int]:
        v = self.viewer or {}
        return (
            int(v.get("samples_per_task_all", 3)),
            int(v.get("samples_per_task_filtered", 6)),
        )

    def fingerprint_param_keys(self) -> list[str]:
        keys = (self.fingerprint or {}).get("param_keys")
        if keys:
            return list(keys)
        return [p["key"] for p in self.params if p.get("key")]

    def to_console_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "intro": self.intro,
            "eval_mode": self.eval_mode,
            "param_groups": self.param_groups or {
                "data": "数据范围",
                "inference": "生成参数",
                "eval": "评测参数",
                "advanced": "高级",
            },
            "params": self.params,
            "data_root": f"data/{self.data_subdir}",
            "output_subdir": self.output_subdir,
        }
