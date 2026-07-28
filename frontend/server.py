#!/usr/bin/env python3
"""Multi-image eval platform: job console API + sample viewer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

PROJECT_ROOT = Path(
    os.environ.get("MULTI_IMAGE_EVAL_ROOT", Path(__file__).resolve().parents[1])
).resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from core.benchmark.loader import discover_benchmark_ids, load_manifest, load_plugin_module  # noqa: E402
from core.console.options import get_benchmark_options  # noqa: E402
from core.console.versions import list_benchmark_versions  # noqa: E402
from core.dataset.info import get_dataset_info  # noqa: E402
from core.env import python_bin, runtime_env  # noqa: E402
from core.gpu import gpu_summary  # noqa: E402
from core.judge.config import get_judge_config_public, list_models_from_gateway, write_judge_config  # noqa: E402
from core.jobs.control import resume_job, stop_job  # noqa: E402
from core.jobs.manager import export_job_samples, get_job, launch_job, list_jobs, delete_job  # noqa: E402
from core.jobs.viewer_data import get_job_viewer_data  # noqa: E402
from core.paths import VIEWER_DATA_DIR  # noqa: E402
from core.registry import list_viewer_benchmarks, load_benchmark, load_model, load_models, load_weight  # noqa: E402
from core.weights.registry import register_weight, save_weight_upload  # noqa: E402

CONSOLE_DIST = PROJECT_ROOT / "frontend" / "console" / "dist"
SAMPLES_DIST = PROJECT_ROOT / "frontend" / "eval-viewer" / "dist"

app = FastAPI(title="Multi-Image Eval Platform")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_console_index(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path in ("", "/") or path.endswith("/index.html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


class LaunchRequest(BaseModel):
    model_id: str = ""
    weight_id: str = ""
    benchmark: str
    model_path: str
    gpus: list[int] = Field(..., min_length=1)
    params: dict = Field(default_factory=dict)


class JudgeConfigRequest(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class JudgeModelsRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = None


class ResumeRequest(BaseModel):
    gpus: list[int] = Field(..., min_length=1)


def _viewer_cfg(benchmark_id: str) -> dict:
    for cfg in list_viewer_benchmarks():
        if cfg["id"] == benchmark_id:
            return cfg
    raise KeyError(benchmark_id)


@app.get("/api/console/models")
def api_models():
    return load_models()


@app.post("/api/dataset/download")
def api_download_dataset(
    benchmark: str = Query("multibanana"),
    full: bool = Query(True),
    samples_per_task: int = Query(0),
):
    try:
        manifest = load_manifest(benchmark)
    except KeyError:
        raise HTTPException(404, f"Unknown benchmark: {benchmark}") from None

    script = manifest.script_path("download")
    if not script or not script.exists():
        raise HTTPException(400, f"Download not supported for {benchmark}")

    log_path = PROJECT_ROOT / "logs" / f"download_{benchmark}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = runtime_env()
    per_task = 0 if full else max(1, samples_per_task)
    with open(log_path, "a", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            [python_bin(), str(script), "--samples-per-task", str(per_task)],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return {
        "started": True,
        "pid": proc.pid,
        "log": str(log_path.relative_to(PROJECT_ROOT)),
        "samples_per_task": per_task,
    }


@app.get("/api/console/benchmarks")
def api_console_benchmarks():
    return load_benchmark()


@app.get("/api/console/benchmark-options")
def api_benchmark_options(benchmark: str = Query(...)):
    try:
        load_benchmark(benchmark)
    except KeyError:
        raise HTTPException(404, f"Unknown benchmark: {benchmark}") from None
    return get_benchmark_options(benchmark)


@app.get("/api/console/versions")
def api_benchmark_versions(
    model_id: str = Query(...),
    weight_id: str = Query(...),
    benchmark: str = Query(...),
):
    try:
        load_benchmark(benchmark)
        load_weight(model_id, weight_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from None
    return list_benchmark_versions(
        model_id=model_id,
        weight_id=weight_id,
        benchmark=benchmark,
    )


@app.post("/api/console/dataset-info")
def api_dataset_info_post(body: dict):
    benchmark = body.get("benchmark")
    if not benchmark:
        raise HTTPException(400, "benchmark required")
    try:
        load_benchmark(benchmark)
    except KeyError:
        raise HTTPException(404, f"Unknown benchmark: {benchmark}") from None
    return get_dataset_info(benchmark, body.get("params") or {})


@app.get("/api/console/dataset-info")
def api_dataset_info(
    benchmark: str = Query("multibanana"),
    dataset_mode: str = Query("full"),
    samples_per_task: int = Query(2),
    task_types: str = Query(""),
):
    try:
        load_benchmark(benchmark)
    except KeyError:
        raise HTTPException(404, f"Unknown benchmark: {benchmark}") from None
    task_list = [t.strip() for t in task_types.split(",") if t.strip()]
    return get_dataset_info(benchmark, {
        "dataset_mode": dataset_mode,
        "samples_per_task": samples_per_task,
        "task_types": task_list,
    })


@app.get("/api/console/gpus")
def api_gpus():
    return gpu_summary()


@app.get("/api/console/judge-config")
def api_judge_config_get():
    return get_judge_config_public(PROJECT_ROOT)


@app.post("/api/console/judge-config")
def api_judge_config_post(req: JudgeConfigRequest):
    try:
        return write_judge_config(
            PROJECT_ROOT,
            api_key=req.api_key,
            base_url=req.base_url,
            model=req.model,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/console/judge-models")
def api_judge_models(req: JudgeModelsRequest):
    try:
        models = list_models_from_gateway(req.base_url, req.api_key)
        return {"models": models}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/console/weights")
async def api_register_weight(
    model_id: str = Form(...),
    label: str = Form(...),
    path: str = Form(""),
    weight_file: UploadFile | None = File(None),
):
    try:
        load_model(model_id)
    except KeyError:
        raise HTTPException(404, f"Unknown model: {model_id}") from None

    final_path = path.strip()
    source = "path"
    if weight_file and weight_file.filename:
        import tempfile

        suffix = Path(weight_file.filename).suffix or ".safetensors"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await weight_file.read())
            tmp_path = Path(tmp.name)
        try:
            final_path = str(save_weight_upload(weight_file.filename, tmp_path))
            source = "upload"
        finally:
            tmp_path.unlink(missing_ok=True)

    try:
        weight = register_weight(model_id=model_id, label=label, path=final_path, source=source)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return weight


@app.get("/api/jobs")
def api_list_jobs():
    return list_jobs()


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/jobs/{job_id}/viewer-data")
def api_job_viewer_data(
    job_id: str,
    task: str = Query(""),
    limit: int = Query(48, ge=1, le=200),
):
    try:
        return get_job_viewer_data(job_id, task=task, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc


@app.post("/api/jobs")
def api_launch_job(req: LaunchRequest):
    try:
        load_benchmark(req.benchmark)
    except KeyError:
        raise HTTPException(404, f"Unknown benchmark: {req.benchmark}") from None
    model_path = req.model_path
    if req.model_id and req.weight_id:
        try:
            model_path = load_weight(req.model_id, req.weight_id)["path"]
        except KeyError:
            raise HTTPException(404, "Model weight not found") from None
    try:
        payload = req.model_dump()
        payload["model_path"] = model_path
        if req.model_id:
            payload["model_id"] = req.model_id
        if req.weight_id:
            payload["weight_id"] = req.weight_id
        return launch_job(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/jobs/{job_id}/resume")
def api_resume_job(job_id: str, req: ResumeRequest):
    try:
        return resume_job(job_id, req.gpus)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/jobs/{job_id}/cancel")
def api_cancel_job(job_id: str):
    try:
        job = stop_job(job_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.delete("/api/jobs/{job_id}")
def api_delete_job(job_id: str):
    try:
        return delete_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/jobs/{job_id}/export-samples")
def api_export_samples(job_id: str):
    try:
        return export_job_samples(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, f"Export failed: {exc}") from exc


# --- Sample viewer APIs (read-only) ---

@app.get("/api/benchmarks")
def api_list_viewer_benchmarks():
    out = []
    for cfg in list_viewer_benchmarks():
        data_path = VIEWER_DATA_DIR / cfg["data_file"]
        out.append({
            "id": cfg["id"],
            "title": cfg["title"],
            "available": data_path.exists(),
        })
    return out


@app.get("/api/data")
def get_data(bench: str = Query("multibanana")):
    try:
        cfg = _viewer_cfg(bench)
    except KeyError:
        raise HTTPException(404, f"Unknown benchmark: {bench}") from None
    data_path = VIEWER_DATA_DIR / cfg["data_file"]
    if not data_path.exists():
        raise HTTPException(404, f"{data_path.name} not found")
    return json.loads(data_path.read_text(encoding="utf-8"))


def _resolve_image(bench: str, path: str) -> Path:
    try:
        manifest = load_manifest(bench)
    except KeyError:
        raise HTTPException(404, f"Unknown benchmark: {bench}") from None
    plugin = load_plugin_module(bench)
    if hasattr(plugin, "resolve_image"):
        resolved = plugin.resolve_image(manifest, path)
        if resolved:
            return resolved
    candidate = PROJECT_ROOT / path
    if candidate.exists() and candidate.is_file():
        return candidate
    raise HTTPException(404, f"Image not found: {path}")


def _resolve_image_any(path: str) -> Path:
    """Resolve image path by trying each benchmark plugin, then PROJECT_ROOT."""
    for bid in discover_benchmark_ids():
        try:
            return _resolve_image(bid, path)
        except HTTPException:
            continue
    raise HTTPException(404, f"Image not found: {path}")


@app.get("/images/{bench}/{path:path}")
def get_image_bench(bench: str, path: str):
    if bench in discover_benchmark_ids():
        return FileResponse(_resolve_image(bench, path))
    # /images/data/... or /images/outputs/... — first segment is not a benchmark id
    return FileResponse(_resolve_image_any(f"{bench}/{path}"))


@app.get("/images/{path:path}")
def get_image(path: str, bench: str = Query("")):
    if bench:
        return FileResponse(_resolve_image(bench, path))
    return FileResponse(_resolve_image_any(path))


# Static: samples viewer at /samples, console at /
if SAMPLES_DIST.exists():
    app.mount("/samples", StaticFiles(directory=str(SAMPLES_DIST), html=True), name="samples")

if CONSOLE_DIST.exists():
    app.mount("/", StaticFiles(directory=str(CONSOLE_DIST), html=True), name="console")
elif SAMPLES_DIST.exists():
    app.mount("/", StaticFiles(directory=str(SAMPLES_DIST), html=True), name="fallback")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("VIEWER_PORT", "8765")))
