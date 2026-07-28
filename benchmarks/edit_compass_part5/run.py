#!/usr/bin/env python3
"""Edit-Compass Part5 runner — wraps external pipeline_runner with console progress."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.edit_compass_part5.data_utils import PART5_TASKS, scope_items  # noqa: E402
from benchmarks.edit_compass_part5.plugin import measure_progress  # noqa: E402
from core.benchmark.loader import load_manifest  # noqa: E402
from core.paths import resolve_pipeline_job_db  # noqa: E402
from core.runner.progress import JobProgress  # noqa: E402

DEFAULT_EC_ROOT = os.environ.get("EDIT_COMPASS_ROOT", "").strip()


def resolve_ec_python(ec_root: Path) -> str:
    """Resolve Python for pipeline subprocess (exec only — never modifies that venv)."""
    candidates = [
        os.environ.get("EDIT_COMPASS_PYTHON", "").strip(),
        os.environ.get("MULTI_IMAGE_EVAL_PYTHON", "").strip(),
        str(Path.home() / "work" / "edit-compass-part5" / ".venv" / "bin" / "python"),
    ]
    for py in candidates:
        if py and Path(py).is_file():
            return py
    return sys.executable


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Edit-Compass Part5 console runner")
    p.add_argument("--data-root", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--model-path", required=True)
    p.add_argument("--progress-file", default="")
    p.add_argument("--subset", type=int, default=0)
    p.add_argument("--tasks", nargs="*", default=None)
    p.add_argument("--language", choices=["en", "cn"], default="en")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--num-inference-steps", type=int, default=40)
    p.add_argument("--eval-workers", type=int, default=8)
    p.add_argument("--gpus", default="")
    p.add_argument("--full-gpu", action="store_true")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--infer-only", action="store_true")
    p.add_argument("--eval-only", action="store_true")
    p.add_argument("--eval-model", default="")
    p.add_argument("--api-key", default="")
    p.add_argument("--api-base", default="")
    p.add_argument("--ec-root", default=str(DEFAULT_EC_ROOT))
    return p.parse_args()


def _sqlite_connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    return conn


def _sqlite_retryable(exc: sqlite3.OperationalError) -> bool:
    msg = str(exc).lower()
    return "lock" in msg or "busy" in msg


def _latest_job_id(db_path: Path) -> str | None:
    if not db_path.is_file():
        return None
    last_err: sqlite3.OperationalError | None = None
    for attempt in range(6):
        try:
            conn = _sqlite_connect(db_path)
            try:
                row = conn.execute(
                    "SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                return row[0] if row else None
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            if not _sqlite_retryable(exc):
                raise
            last_err = exc
            time.sleep(min(0.1 * (2**attempt), 1.0))
    if last_err is not None:
        raise last_err
    return None


def _poll_counts(db_path: Path, job_id: str) -> dict[str, int]:
    last_err: sqlite3.OperationalError | None = None
    for attempt in range(6):
        try:
            conn = _sqlite_connect(db_path)
            try:
                rows = conn.execute(
                    "SELECT status, COUNT(*) AS c FROM samples WHERE job_id = ? GROUP BY status",
                    (job_id,),
                ).fetchall()
            finally:
                conn.close()
            out = {r[0]: r[1] for r in rows}
            out["total"] = sum(out.values())
            return out
        except sqlite3.OperationalError as exc:
            if not _sqlite_retryable(exc):
                raise
            last_err = exc
            time.sleep(min(0.1 * (2**attempt), 1.0))
    if last_err is not None:
        raise last_err
    return {"total": 0}


def _progress_from_counts(c: dict[str, int], *, infer_only: bool) -> tuple[int, int]:
    infer_done = int(c.get("infer_done", 0))
    eval_done = int(c.get("eval_done", 0))
    skipped = int(c.get("skipped", 0))

    gen_done = infer_done + skipped
    if infer_only:
        eval_done = gen_done
    return gen_done, eval_done


def _completion_message(c: dict[str, int], total: int) -> tuple[str, str]:
    """Return (phase, message) after pipeline exits."""
    failed = int(c.get("failed", 0))
    infer_done = int(c.get("infer_done", 0))
    skipped = int(c.get("skipped", 0))
    gen_done = infer_done + skipped
    if failed > 0 and gen_done == 0:
        return "failed", f"推理全部失败 ({failed}/{total})"
    if failed > 0:
        return "done", f"完成（{gen_done}/{total} 成功，{failed} 失败）"
    return "done", "完成"


def _write_eval_summary(
    output_dir: Path,
    model_path: str,
    language: str,
    *,
    infer_only: bool,
) -> None:
    model_name = Path(model_path.rstrip("/")).name
    src = output_dir / model_name / f"part5_summary_{language}.json"
    out = output_dir / "eval_part5.json"
    if src.is_file():
        payload = json.loads(src.read_text(encoding="utf-8"))
    else:
        payload = {
            "language": language,
            "model": model_name,
            "tasks": {},
            "part5_average": None,
        }
    summary = {
        "benchmark": "edit_compass_part5",
        "model": model_name,
        "language": language,
        "infer_only": infer_only,
        "part5": payload,
        "avg_score": payload.get("part5_average"),
    }
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.infer_only and args.eval_only:
        raise SystemExit("Cannot use --infer-only and --eval-only together")

    ec_root = Path(args.ec_root).expanduser().resolve() if args.ec_root else None
    if not ec_root or not ec_root.is_dir():
        raise SystemExit(
            "EDIT_COMPASS_ROOT is not set or invalid. "
            "Set env EDIT_COMPASS_ROOT or pass --ec-root to Edit-Compass Part5 project."
        )
    pipeline = ec_root / "src" / "pipeline_runner.py"
    if not pipeline.is_file():
        raise SystemExit(f"pipeline_runner not found: {pipeline}")

    data_root = Path(args.data_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    job_db = resolve_pipeline_job_db(output_dir)

    tasks = args.tasks or PART5_TASKS
    items = scope_items(
        data_root,
        task_types=list(tasks),
        subset=int(args.subset),
        seed=int(args.seed),
    )
    total = len(items)
    if total == 0:
        raise SystemExit("No samples in scope")

    manifest = load_manifest("edit_compass_part5")
    run_params = {
        "task_types": list(tasks),
        "dataset_mode": "full" if int(args.subset) == 0 else "smoke",
        "samples_per_task": int(args.subset) or 1,
        "seed": int(args.seed),
        "language": args.language,
    }
    try:
        disk = measure_progress(manifest, output_dir, args.model_path, run_params)
    except Exception:
        disk = {}
    baseline_gen = int(disk.get("gen_done", 0))
    baseline_eval = int(disk.get("eval_done", 0))

    def _merge_disk_progress(gen_done: int, eval_done: int) -> tuple[int, int]:
        """Keep progress monotonic: SQLite poll and CPFS listing can disagree briefly."""
        try:
            live = measure_progress(manifest, output_dir, args.model_path, run_params)
        except Exception:
            live = {}
        return (
            max(baseline_gen, gen_done, int(live.get("gen_done", 0))),
            max(baseline_eval, eval_done, int(live.get("eval_done", 0))),
        )

    progress = JobProgress(total, total, pipeline=not args.infer_only)
    progress.gen_done = baseline_gen
    progress.eval_done = baseline_eval
    progress_path = args.progress_file or None
    if baseline_gen > 0 or args.skip_existing:
        boot_msg = (
            f"已有 {baseline_gen}/{total} 张（磁盘统计）"
            f" · 评测 {baseline_eval}/{total}"
            " · 正在加载模型…"
        )
    else:
        boot_msg = "启动 Edit-Compass Part5 流水线…"
    progress.set_phase("loading_model", progress_path, boot_msg)

    py = resolve_ec_python(ec_root)
    cmd = [
        py,
        str(pipeline),
        "--model-path", args.model_path,
        "--data-root", str(data_root),
        "--results-dir", str(output_dir),
        "--language", args.language,
        "--subset", str(args.subset),
        "--seed", str(args.seed),
        "--num-inference-steps", str(args.num_inference_steps),
        "--eval-workers", str(args.eval_workers),
        "--job-db", str(job_db),
    ]
    if args.tasks:
        cmd.extend(["--tasks", *args.tasks])
    if args.gpus:
        cmd.extend(["--gpus", args.gpus])
    if args.full_gpu:
        cmd.append("--full-gpu")
    if args.skip_existing:
        cmd.append("--skip-existing")
    if args.infer_only:
        cmd.append("--infer-only")
    if args.eval_only:
        cmd.append("--eval-only")
    if args.eval_model:
        cmd.extend(["--eval-model", args.eval_model])
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    api_base = args.api_base or os.environ.get("OPENAI_BASE_URL") or os.environ.get("GEMINI_BASE_URL", "")
    if api_key:
        cmd.extend(["--api-key", api_key])
    if api_base:
        cmd.extend(["--api-base", api_base])

    shutting_down = False

    proc = subprocess.Popen(
        cmd,
        cwd=str(ec_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    def _shutdown(signum, _frame):
        nonlocal shutting_down
        if shutting_down:
            raise SystemExit(128 + signum)
        shutting_down = True
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except OSError:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except OSError:
                    proc.kill()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    pipeline_job_id: str | None = None
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")
        if pipeline_job_id is None:
            marker = "Job "
            if line.startswith(marker) and ":" in line:
                pipeline_job_id = line.split(marker, 1)[1].split(":", 1)[0].strip()
        if pipeline_job_id is None and job_db.exists():
            pipeline_job_id = _latest_job_id(job_db)
        if pipeline_job_id and job_db.exists():
            try:
                c = _poll_counts(job_db, pipeline_job_id)
            except sqlite3.OperationalError:
                continue
            gen_done, eval_done = _progress_from_counts(c, infer_only=args.infer_only)
            gen_done, eval_done = _merge_disk_progress(gen_done, eval_done)
            with progress._lock:
                progress.gen_done = gen_done
                progress.eval_done = eval_done
                progress._sync_phase()
                if progress.phase == "pipeline":
                    progress.message = (
                        f"流水线：出图 {gen_done}/{total} · 评测 {eval_done}/{total}"
                    )
                elif progress.phase == "generating":
                    progress.message = f"生成中 {gen_done}/{total}"
                elif progress.phase == "evaluating":
                    progress.message = f"评测中 {eval_done}/{total}"
            progress.write(progress_path)

    rc = proc.wait()
    if rc != 0:
        progress.set_phase("failed", progress_path, f"pipeline 退出码 {rc}")
        raise SystemExit(rc)

    if pipeline_job_id and job_db.exists():
        c = _poll_counts(job_db, pipeline_job_id)
        gen_done, eval_done = _progress_from_counts(c, infer_only=args.infer_only)
        gen_done, eval_done = _merge_disk_progress(gen_done, eval_done)
        phase, message = _completion_message(c, total)
        with progress._lock:
            progress.gen_done = gen_done
            progress.eval_done = eval_done
            progress.phase = phase
            progress.message = message
        progress.write(progress_path)
        if phase == "failed":
            raise SystemExit(1)

    _write_eval_summary(
        output_dir,
        args.model_path,
        args.language,
        infer_only=args.infer_only,
    )
    print(f"Wrote {output_dir / 'eval_part5.json'}")


if __name__ == "__main__":
    main()
