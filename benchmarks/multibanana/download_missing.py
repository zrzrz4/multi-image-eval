#!/usr/bin/env python3
"""Download missing files via official HuggingFace (with token)."""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.env import apply_dotenv

apply_dotenv()
# Official HF only — mirror breaks hf_hub_download for this dataset.
os.environ.pop("HF_ENDPOINT", None)
os.environ.pop("HUGGINGFACE_HUB_ENDPOINT", None)

from benchmarks.multibanana.data_utils import HF_REPO
from benchmarks.multibanana.download_parallel import list_repo_files

from huggingface_hub import hf_hub_download


def main() -> None:
    local_dir = Path(os.environ.get("HF_LOCAL_DIR", PROJECT_ROOT / "data/multibanana/hf_repo"))
    workers = int(os.environ.get("HF_DOWNLOAD_WORKERS", "16"))
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    all_files = list_repo_files()
    missing = [rel for rel in all_files if not (local_dir / rel).exists() or (local_dir / rel).stat().st_size == 0]
    print(f"[missing] {len(missing)} / {len(all_files)} files", flush=True)
    if not missing:
        return

    def dl(rel: str) -> None:
        dst = local_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        cached = hf_hub_download(
            repo_id=HF_REPO,
            filename=rel,
            repo_type="dataset",
            token=token,
        )
        dst.write_bytes(Path(cached).read_bytes())

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(dl, rel): rel for rel in missing}
        for i, fut in enumerate(as_completed(futs), 1):
            rel = futs[fut]
            try:
                fut.result()
                ok += 1
            except Exception as exc:
                fail += 1
                print(f"[fail] {rel}: {exc}", flush=True)
            if i % 100 == 0:
                print(f"[progress] {i}/{len(missing)} ok={ok} fail={fail}", flush=True)

    print(f"[done] ok={ok} fail={fail}", flush=True)
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
