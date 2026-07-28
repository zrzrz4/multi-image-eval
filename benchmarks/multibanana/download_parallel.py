#!/usr/bin/env python3
"""Parallel dataset download via hf-mirror (multi-shard + thread pool)."""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.env import apply_dotenv  # noqa: E402

apply_dotenv()

from benchmarks.multibanana.data_utils import HF_REPO, build_file_index  # noqa: E402


def list_repo_files() -> list[str]:
    task_types, by_task, _ = build_file_index()
    out: list[str] = []
    for task in task_types:
        for name in by_task[task]:
            out.append(f"{task}/{name}")
    return out


def mirror_url(rel_path: str, official: bool = False) -> str:
    if official:
        return f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/{rel_path}"
    base = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com").rstrip("/")
    return f"{base}/datasets/{HF_REPO}/resolve/main/{rel_path}"


def download_one(rel_path: str, local_dir: Path, token: str | None) -> str:
    dst = local_dir / rel_path
    if dst.exists() and dst.stat().st_size > 0:
        return "skip"
    dst.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for attempt in range(5):
        official = attempt >= 2
        req = urllib.request.Request(mirror_url(rel_path, official=official))
        req.add_header("User-Agent", "multi-image-eval/parallel")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                dst.write_bytes(resp.read())
            return "ok"
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            if exc.code == 404 and not official:
                continue
            time.sleep(0.5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"failed {rel_path}: {last_err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel MultiBanana download")
    parser.add_argument("--local-dir", required=True)
    parser.add_argument("--workers", type=int, default=int(os.environ.get("HF_DOWNLOAD_WORKERS", "48")))
    parser.add_argument("--shard", type=int, default=int(os.environ.get("PARALLEL_SHARD", "0")))
    parser.add_argument("--shards", type=int, default=int(os.environ.get("PARALLEL_SHARDS", "1")))
    args = parser.parse_args()

    local_dir = Path(args.local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    all_files = list_repo_files()
    shard_files = [f for i, f in enumerate(all_files) if i % args.shards == args.shard]
    print(
        f"[shard {args.shard}/{args.shards}] files={len(shard_files)} workers={args.workers} "
        f"endpoint={os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')}",
        flush=True,
    )

    done = skip = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(download_one, rel, local_dir, token): rel for rel in shard_files}
        for i, fut in enumerate(as_completed(futures), 1):
            rel = futures[fut]
            try:
                status = fut.result()
                if status == "skip":
                    skip += 1
                else:
                    done += 1
            except Exception as exc:
                fail += 1
                print(f"[fail] {rel}: {exc}", flush=True)
            if i % 200 == 0 or i == len(shard_files):
                elapsed = max(time.time() - t0, 1)
                rate = i / elapsed
                print(
                    f"[progress] {i}/{len(shard_files)} ok={done} skip={skip} fail={fail} "
                    f"{rate:.1f} files/s",
                    flush=True,
                )

    print(f"[done] shard {args.shard}: ok={done} skip={skip} fail={fail}", flush=True)
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
