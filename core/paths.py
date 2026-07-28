"""Project-wide path helpers (benchmark-agnostic)."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("MULTI_IMAGE_EVAL_ROOT", Path(__file__).resolve().parents[1])
).resolve()

CONFIG_DIR = PROJECT_ROOT / "config"
BENCHMARKS_DIR = PROJECT_ROOT / "benchmarks"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
JOBS_DIR = PROJECT_ROOT / "jobs"
LOGS_DIR = PROJECT_ROOT / "logs"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
VIEWER_DATA_DIR = FRONTEND_DIR / "viewer_data"


def benchmark_package_dir(benchmark_id: str) -> Path:
    return BENCHMARKS_DIR / benchmark_id


def benchmark_data_dir(benchmark_id: str) -> Path:
    return DATA_DIR / benchmark_id


def benchmark_outputs_dir(benchmark_id: str) -> Path:
    return OUTPUTS_DIR / benchmark_id


def job_output_dir(benchmark_id: str, job_id: str) -> Path:
    return benchmark_outputs_dir(benchmark_id) / job_id


def job_log_dir(job_id: str) -> Path:
    return LOGS_DIR / job_id


def viewer_json_path(benchmark_id: str) -> Path:
    return VIEWER_DATA_DIR / f"{benchmark_id}.json"


def resolve_job_output_dir(job: dict) -> Path:
    """Resolve job output dir for local install or CPFS public archive."""
    archive = (job.get("public_archive_dir") or "").strip()
    if archive:
        archive_path = Path(archive)
        nested = archive_path / job["output_dir"]
        if nested.is_dir():
            return nested
        # Public sync often flattens to {archive}/outputs/ (without benchmark/job subdirs).
        flat = archive_path / "outputs"
        if flat.is_dir():
            return flat
        return nested
    return PROJECT_ROOT / job["output_dir"]


def rel_to_viewer_path(path: Path, *, archive_base: Path | None = None) -> str:
    """Prefer install-relative paths; fall back to archive-relative or absolute."""
    resolved = path.resolve()
    for base in (PROJECT_ROOT, archive_base):
        if base is None:
            continue
        try:
            return str(resolved.relative_to(base.resolve())).replace("\\", "/")
        except ValueError:
            continue
    return str(resolved)


def resolve_viewer_image(
    path: str,
    *,
    data_dir: Path | None = None,
    project_root: Path | None = None,
    extra_roots: list[Path] | None = None,
) -> Path | None:
    """Resolve a viewer image path for local install or CPFS public archive."""
    if not path or str(path).startswith(("http://", "https://")):
        return None
    p = Path(path)
    if p.is_absolute() and p.is_file():
        return p
    root = project_root or PROJECT_ROOT
    candidate = root / path
    if candidate.is_file():
        return candidate
    if data_dir is not None:
        nested = data_dir / path
        if nested.is_file():
            return nested
    for extra in extra_roots or []:
        ext = extra / path
        if ext.is_file():
            return ext
    # Console imgUrl strips leading "/" from absolute CPFS paths before /images/...
    abs_guess = Path("/") / path
    if abs_guess.is_file():
        return abs_guess
    if path.startswith("outputs/"):
        from core.jobs.public_archive import iter_public_job_dirs

        for archive_dir, _host in iter_public_job_dirs():
            archived = archive_dir / path
            if archived.is_file():
                return archived
    return None


def local_state_dir() -> Path:
    """Writable local dir for SQLite etc. (never use CPFS/NFS for job DBs)."""
    raw = os.environ.get("MIE_LOCAL_STATE_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".cache" / "multi-image-eval").resolve()


def resolve_pipeline_job_db(output_dir: Path, *, filename: str = "pipeline_jobs.db") -> Path:
    """Map a job output dir (CPFS or local) to a stable SQLite path on local disk."""
    output_dir = output_dir.resolve()
    if output_dir.name.startswith("job_"):
        key = output_dir.name
    else:
        import hashlib

        key = hashlib.sha256(str(output_dir).encode()).hexdigest()[:16]
    db_dir = local_state_dir() / "pipeline_dbs" / key
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / filename
