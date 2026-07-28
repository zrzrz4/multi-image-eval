# HuggingFace 数据集/模型加速下载（国内）

适用于从 HuggingFace 拉取数据集或模型。核心思路：**别用单线程 API 逐个下文件，改用镜像 + 多连接并行拉直链**。

---

## 为什么慢？

| 慢的方式 | 原因 |
|----------|------|
| `huggingface_hub.hf_hub_download()` 循环调用 | 每个文件一次 API 往返，无法吃满带宽 |
| Python 单进程顺序下载 | 8～9 GB 往往要 **数小时** |
| 只设了 `HF_ENDPOINT` 但仍用 hub API | 部分仓库镜像对 API 不兼容，会跳官方或报错 |

| 快的方式 | 原因 |
|----------|------|
| **hfd**（镜像 + wget 多线程） | 批量生成 URL 列表，10 连接同时拉 |
| **分片 + 线程池 + 直链** | 多进程分片，每片几十线程，直链下镜像 |

实测：~9 GB 数据集，单进程约 **4～5 小时** → 并行方案约 **15～30 分钟**。

---

## 前置准备

### 1. 镜像（国内必配）

```bash
export HF_ENDPOINT=https://hf-mirror.com
# 写入 ~/.bashrc 持久化
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.bashrc
```

### 2. Token（建议）

[https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) 创建 **Read** token：

```bash
export HF_TOKEN=hf_xxxxxxxx
export HUGGING_FACE_HUB_TOKEN=$HF_TOKEN
```

有 Token 可提高限速配额；Gated 仓库必须带 Token。

### 3. 依赖

```bash
pip install -U huggingface_hub
# hfd 方案只需 wget，无需额外 pip
```

---

## 方法一：hfd（最简单，推荐入门）

[hfd](https://hf-mirror.com) 是镜像站提供的批量下载工具，基于 wget 多连接。

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_TOKEN=hf_xxxxxxxx          # 可选

# 下载 hfd
wget https://hf-mirror.com/hfd/hfd.sh
chmod +x hfd.sh

# 下载数据集
./hfd.sh <org>/<dataset-name> --dataset --tool wget -x 10 --local-dir ./data

# 下载模型
./hfd.sh <org>/<model-name> --tool wget -x 10 --local-dir ./model
```

| 参数 | 说明 |
|------|------|
| `-x 10` | 并发连接数，**最大 10** |
| `--dataset` | 数据集（不加则为 model） |
| `--local-dir` | 本地目录，支持断点续传（重跑即可） |

**优点：** 零代码、自动列文件、断点续传。  
**缺点：** 单进程，超大仓库仍偏慢（约 1～2 小时级）。

---

## 方法二：huggingface-cli（官方工具 + 镜像）

```bash
export HF_ENDPOINT=https://hf-mirror.com

huggingface-cli download \
  --repo-type dataset \
  --resume-download \
  <org>/<dataset-name> \
  --local-dir ./data \
  --local-dir-use-symlinks False
```

模型去掉 `--repo-type dataset` 即可。

适合中等规模；大仓库仍不如并行直链快。

---

## 方法三：分片 + 多线程直链（最快）

思路：

1. 用 HF API **列出仓库所有文件**（只调一次索引）
2. 拼镜像直链：`{HF_ENDPOINT}/datasets/{repo}/resolve/main/{path}`
3. **N 个进程分片**，每片内 **M 个线程** 并发 `GET`
4. 已存在且非空的文件 **跳过**（断点续传）

直链格式：

```
# 数据集
https://hf-mirror.com/datasets/<org>/<name>/resolve/main/<file-path>

# 模型
https://hf-mirror.com/<org>/<name>/resolve/main/<file-path>
```

### 通用 Python 模板

```python
#!/usr/bin/env python3
"""并行下载 HF 仓库（数据集/模型均可）。"""
import os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from huggingface_hub import HfApi

REPO_ID = "kohsei/MultiBanana-Benchmark"   # 改成你的仓库
REPO_TYPE = "dataset"                       # 模型用 "model"
LOCAL_DIR = Path("./hf_repo")
SHARD = int(os.environ.get("PARALLEL_SHARD", "0"))
SHARDS = int(os.environ.get("PARALLEL_SHARDS", "1"))
WORKERS = int(os.environ.get("HF_DOWNLOAD_WORKERS", "32"))
ENDPOINT = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com").rstrip("/")
TOKEN = os.environ.get("HF_TOKEN")

def list_files():
    api = HfApi(endpoint=ENDPOINT)
    return api.list_repo_files(REPO_ID, repo_type=REPO_TYPE)

def url_for(rel: str) -> str:
    kind = "datasets" if REPO_TYPE == "dataset" else "models"
    if REPO_TYPE == "model":
        return f"{ENDPOINT}/{REPO_ID}/resolve/main/{rel}"
    return f"{ENDPOINT}/datasets/{REPO_ID}/resolve/main/{rel}"

def download_one(rel: str) -> str:
    dst = LOCAL_DIR / rel
    if dst.exists() and dst.stat().st_size > 0:
        return "skip"
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url_for(rel))
    req.add_header("User-Agent", "hf-parallel-download")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                dst.write_bytes(r.read())
            return "ok"
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(rel)

def main():
    files = list_files()
    mine = [f for i, f in enumerate(files) if i % SHARDS == SHARD]
    print(f"shard {SHARD}/{SHARDS}: {len(mine)} files, {WORKERS} workers")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(download_one, f): f for f in mine}
        for fut in as_completed(futs):
            fut.result()

if __name__ == "__main__":
    main()
```

### 启动多分片（bash）

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_TOKEN=hf_xxxxxxxx
export HF_DOWNLOAD_WORKERS=40

LOCAL_DIR=./hf_repo
mkdir -p "$LOCAL_DIR" logs

for i in $(seq 0 7); do
  PARALLEL_SHARD=$i PARALLEL_SHARDS=8 \
    python download_parallel.py >> "logs/shard${i}.log" 2>&1 &
done

# 查看进度
tail -f logs/shard0.log
find "$LOCAL_DIR" -type f | wc -l
du -sh "$LOCAL_DIR"
```

等所有 shard 日志结束即可。

---

## 参数怎么调？

| 场景 | 建议 |
|------|------|
| 网络一般 / 怕限流 | hfd `-x 10`，或并行 `--shards 4 --workers 24` |
| 追求速度 | `--shards 8 --workers 40` |
| 出现 **429** | 降低 `workers` 或 `shards`，不要叠多个下载任务 |

**切忌：** 同时跑多个 hfd / 多套并行脚本，会互抢带宽且容易 429。

---

## 常见问题

**Q：`HF_ENDPOINT` 设了，`hf_hub_download` 还是慢或报错？**  
A：镜像对 hub Python API 支持不完整。快下请用 **hfd** 或 **直链多线程**，不要依赖 `hf_hub_download` 循环。

**Q：hfd 报 `threads (-x) must be 1-10`？**  
A：`-x` 上限是 10，不能更大。要更快请用方法三多分片。

**Q：如何断点续传？**  
A：hfd / 并行脚本均跳过已存在文件，**原命令再跑一遍**即可。

**Q：Gated 仓库？**  
A：必须设 `HF_TOKEN`，并在 HF 网页同意许可。

---

## 方案选型

```
小文件 / 偶尔下    →  huggingface-cli + HF_ENDPOINT
省事 / 中等规模    →  hfd.sh  -x 10
大仓库 / 要最快    →  分片 + 线程池直链（方法三）
```

---

## 本仓库中的实现

`multi-image-eval` 里已封装 MultiBanana 的并行下载，用法相同：

```bash
cd ~/work/multi-image-eval
source .env
bash scripts/download_dataset_fast.sh multibanana --shards 8 --workers 40
```

实现文件：

- `scripts/download_dataset_fast.sh` — 启动多分片
- `benchmarks/multibanana/download_parallel.py` — 直链并行核心逻辑

其他 benchmark 可按上文 **方法三模板** 改 `REPO_ID` 复用。
