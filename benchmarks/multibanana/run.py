#!/usr/bin/env python3
"""MultiBanana runner: multi-reference FireRed generate + Gemini judge."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import torch
from PIL import Image
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.multibanana.data_utils import (  # noqa: E402
    filter_metadata,
    load_metadata,
    setup_subset,
)
from benchmarks.multibanana.gemini_judge import evaluate_sample, extract_scores  # noqa: E402
from core.runner.progress import JobProgress, shard_items, write_progress  # noqa: E402
from paths import MODEL_DEFAULT, MULTIBANANA_DATA, MULTIBANANA_OUTPUTS  # noqa: E402

torch.backends.cuda.enable_cudnn_sdp(False)
MIN_IMAGE_BYTES = 1024


def _disk_counts(output_dir: Path, judge_dir: Path, meta: list[dict]) -> tuple[int, int]:
    gen_done = 0
    eval_done = 0
    for item in meta:
        out_path = output_dir / f"{item['key']}.jpg"
        if out_path.is_file() and out_path.stat().st_size >= MIN_IMAGE_BYTES:
            gen_done += 1
        judge_file = judge_dir / f"{item['key']}_gemini_judge.txt"
        if judge_file.is_file():
            scores = extract_scores(judge_file.read_text(encoding="utf-8"))
            if scores:
                eval_done += 1
    return gen_done, eval_done


def load_refs(data_root: Path, item: dict) -> list[Image.Image]:
    return [Image.open(data_root / rel).convert("RGB") for rel in item["reference_paths"]]


def link_for_judge(data_root: Path, item: dict, out_path: Path) -> None:
    task_dir = data_root / "data" / item["task"]
    judge_path = task_dir / f"{item['number']}_generated.jpg"
    if judge_path.exists() or judge_path.is_symlink():
        judge_path.unlink()
    judge_path.symlink_to(out_path.resolve())


def rebuild_eval_summary(data_root: Path, output_dir: Path, judge_dir: Path) -> dict:
    import fcntl

    judge_dir.mkdir(parents=True, exist_ok=True)
    meta = {m["key"]: m for m in load_metadata(data_root)}
    rows = []
    for judge_file in sorted(judge_dir.glob("*_gemini_judge.txt")):
        key = judge_file.name.replace("_gemini_judge.txt", "")
        item = meta.get(key)
        if not item:
            continue
        scores = extract_scores(judge_file.read_text(encoding="utf-8"))
        if scores:
            rows.append({"key": key, "task": item["task"], **scores})
    summary = {
        "benchmark": "MultiBanana",
        "total": len(rows),
        "avg_score": round(sum(r["score"] for r in rows) / len(rows), 3) if rows else None,
        "rows": rows,
    }
    lock_path = output_dir / ".eval_summary.lock"
    out_json = output_dir / "eval_multibanana.json"
    with open(lock_path, "w", encoding="utf-8") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        tmp = out_json.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(out_json)
    return summary


def evaluate_one(
    data_root: Path,
    output_dir: Path,
    judge_dir: Path,
    item: dict,
) -> dict | None:
    judge_dir.mkdir(parents=True, exist_ok=True)
    judge_file = judge_dir / f"{item['key']}_gemini_judge.txt"
    if judge_file.exists():
        scores = extract_scores(judge_file.read_text(encoding="utf-8"))
        if scores:
            return scores
    gen_path = output_dir / f"{item['key']}.jpg"
    if not gen_path.exists() or gen_path.stat().st_size < MIN_IMAGE_BYTES:
        return None
    task_dir = data_root / "data" / item["task"]
    ref_paths = [data_root / rel for rel in item["reference_paths"]]
    prompt_path = task_dir / f"{item['number']}_prompt.txt"
    text = evaluate_sample(gen_path, ref_paths, prompt_path)
    judge_file.write_text(text, encoding="utf-8")
    scores = extract_scores(text)
    if scores:
        rebuild_eval_summary(data_root, output_dir, judge_dir)
    return scores


def _eval_worker(
    data_root: Path,
    output_dir: Path,
    judge_dir: Path,
    item: dict,
    progress: JobProgress | None,
    progress_path: str | None,
) -> dict | None:
    try:
        scores = evaluate_one(data_root, output_dir, judge_dir, item)
    except Exception as exc:
        print(f"  [eval-error] {item['key']}: {exc}")
        scores = None
    if scores and progress:
        progress.bump_eval(
            progress_path,
            f"{item['key']} score={scores.get('score')}",
        )
    print(f"  [eval] {item['key']}: {scores}")
    return scores


def run_generate(
    data_root: Path,
    output_dir: Path,
    model_path: str,
    steps: int,
    seed: int,
    cfg: float,
    progress: JobProgress | None = None,
    progress_path: str | None = None,
    shard_index: int = 0,
    num_shards: int = 1,
    eval_inline: bool = False,
    eval_nproc: int = 8,
    judge_dir: Path | None = None,
    meta: list[dict] | None = None,
):
    from diffusers import QwenImageEditPlusPipeline

    output_dir.mkdir(parents=True, exist_ok=True)
    judge_dir = judge_dir or (output_dir / "judge")

    if progress:
        progress.set_phase("loading_model", progress_path, "模型预热加载中（约 3～8 分钟）")

    pipe = QwenImageEditPlusPipeline.from_pretrained(model_path, torch_dtype=torch.bfloat16)
    pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)

    if progress:
        if eval_inline:
            progress.set_phase("pipeline", progress_path, "流水线：GPU 出图与 Gemini 评测并行")
        else:
            progress.set_phase("generating", progress_path, "模型加载完成，开始生成")

    meta = shard_items(meta or load_metadata(data_root), shard_index, num_shards)
    if num_shards > 1:
        print(f"[shard] {shard_index + 1}/{num_shards} · {len(meta)} samples")

    eval_pool: ThreadPoolExecutor | None = None
    eval_futures = []
    if eval_inline:
        eval_pool = ThreadPoolExecutor(max_workers=max(1, int(eval_nproc)))

    for item in tqdm(meta, desc=f"FireRed MultiBanana[{shard_index}]"):
        out_path = output_dir / f"{item['key']}.jpg"
        if out_path.exists() and out_path.stat().st_size >= MIN_IMAGE_BYTES:
            link_for_judge(data_root, item, out_path)
        else:
            refs = load_refs(data_root, item)
            with torch.inference_mode():
                output = pipe(
                    image=refs,
                    prompt=item["instruction"],
                    generator=torch.Generator(device="cuda").manual_seed(seed),
                    true_cfg_scale=cfg,
                    negative_prompt=" ",
                    num_inference_steps=steps,
                    num_images_per_prompt=1,
                )
            output.images[0].save(out_path, quality=95)
            link_for_judge(data_root, item, out_path)

        if progress:
            progress.bump_gen(progress_path)

        if eval_inline and eval_pool:
            eval_futures.append(
                eval_pool.submit(
                    _eval_worker,
                    data_root,
                    output_dir,
                    judge_dir,
                    item,
                    progress,
                    progress_path,
                )
            )

    if eval_pool:
        for fut in as_completed(eval_futures):
            fut.result()
        eval_pool.shutdown(wait=True)
        if progress:
            progress.write(progress_path)


def run_evaluate_batch(
    data_root: Path,
    output_dir: Path,
    judge_dir: Path,
    nproc: int,
    progress: JobProgress | None = None,
    progress_path: str | None = None,
    meta: list[dict] | None = None,
):
    judge_dir.mkdir(parents=True, exist_ok=True)
    meta = meta or load_metadata(data_root)
    tasks = []
    for item in meta:
        gen_path = output_dir / f"{item['key']}.jpg"
        judge_file = judge_dir / f"{item['key']}_gemini_judge.txt"
        if judge_file.exists() and extract_scores(judge_file.read_text(encoding="utf-8")):
            if progress:
                progress.bump_eval(progress_path)
            continue
        if not gen_path.exists():
            continue
        tasks.append((item, gen_path, judge_file))

    def _one(item):
        scores = evaluate_one(data_root, output_dir, judge_dir, item)
        return item["key"], scores

    if tasks:
        with ThreadPoolExecutor(max_workers=nproc) as pool:
            futures = [pool.submit(_one, item) for item, _, _ in tasks]
            for fut in as_completed(futures):
                key, scores = fut.result()
                if progress:
                    progress.bump_eval(progress_path, key)
                print(f"  {key}: {scores}")

    return rebuild_eval_summary(data_root, output_dir, judge_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=str(MULTIBANANA_DATA))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-path", default=MODEL_DEFAULT)
    parser.add_argument("--samples-per-task", type=int, default=2)
    parser.add_argument("--task-types", default="", help="Comma-separated task types to run")
    parser.add_argument("--setup-data", action="store_true")
    parser.add_argument("--force-setup", action="store_true", help="Re-download metadata even if exists")
    parser.add_argument("--gen-only", action="store_true")
    parser.add_argument("--eval-only", action="store_true")
    parser.add_argument("--no-eval-inline", action="store_true")
    parser.add_argument("--num-inference-steps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=49)
    parser.add_argument("--true-cfg-scale", type=float, default=4.0)
    parser.add_argument("--eval-nproc", type=int, default=8)
    parser.add_argument("--judge-model", default="", help="Override GEMINI_MODEL for eval")
    parser.add_argument("--progress-file", default="")
    parser.add_argument("--parallel-shard", type=int, default=0)
    parser.add_argument("--parallel-shards", type=int, default=1)
    args = parser.parse_args()

    shard_index = max(0, int(args.parallel_shard or 0))
    num_shards = max(1, int(args.parallel_shards or 1))
    eval_inline = not args.gen_only and not args.eval_only and not args.no_eval_inline

    data_root = Path(args.data_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    judge_dir = output_dir / "judge"

    if args.judge_model:
        os.environ["GEMINI_MODEL"] = args.judge_model
        os.environ["BENCHMARK_JUDGE_MODEL"] = args.judge_model

    if args.setup_data or args.force_setup or not (data_root / "metadata.json").exists():
        scope = "full" if args.samples_per_task <= 0 else f"smoke x{args.samples_per_task}"
        print(f"[setup] downloading {scope} -> {data_root}")
        setup_subset(data_root, samples_per_task=args.samples_per_task)

    all_meta = load_metadata(data_root)
    per_task_limit = args.samples_per_task if args.samples_per_task > 0 else 0
    scoped_meta = filter_metadata(all_meta, args.task_types or None, per_task_limit)
    if not scoped_meta:
        raise SystemExit("[error] no samples after task/limit filter — check metadata and --task-types")

    if num_shards > 1 and not args.eval_only:
        shard_meta = shard_items(scoped_meta, shard_index, num_shards)
        gen_total = eval_total = len(shard_meta)
        count_meta = shard_meta
    else:
        gen_total = eval_total = len(scoped_meta)
        count_meta = scoped_meta

    progress = JobProgress(gen_total, eval_total, pipeline=eval_inline)
    baseline_gen, baseline_eval = _disk_counts(output_dir, judge_dir, count_meta)
    progress.gen_done = baseline_gen
    progress.eval_done = baseline_eval
    progress_path = args.progress_file or str(output_dir / "progress.json")
    if baseline_gen > 0 or baseline_eval > 0:
        progress.set_phase(
            "loading_model",
            progress_path,
            f"已有 {baseline_gen}/{gen_total} 张（磁盘统计）· 评测 {baseline_eval}/{eval_total} · 模型加载中…",
        )

    t0 = time.time()
    if not args.eval_only:
        run_generate(
            data_root,
            output_dir,
            args.model_path,
            args.num_inference_steps,
            args.seed,
            args.true_cfg_scale,
            progress,
            progress_path,
            shard_index,
            num_shards,
            eval_inline=eval_inline,
            eval_nproc=args.eval_nproc,
            judge_dir=judge_dir,
            meta=scoped_meta,
        )

    if args.eval_only or (not args.gen_only and not eval_inline):
        progress.set_phase("evaluating", progress_path)
        run_evaluate_batch(
            data_root,
            output_dir,
            judge_dir,
            args.eval_nproc,
            progress,
            progress_path,
            meta=scoped_meta,
        )

    progress.set_phase("done", progress_path, f"finished in {time.time() - t0:.0f}s")
    print(f"[done] output -> {output_dir}")


if __name__ == "__main__":
    main()
