# 数据集下载说明（MultiBanana 全量）

MultiBanana 全量约 **8.9 GB / 10561 文件 / 2229 条样本**。  
慢方法和快方法差在**并行度**和**是否处理镜像限流**，不是数据集变小了。

## 为什么有时很慢、有时很快？

| 方式 | 耗时（经验值） | 原因 |
|------|----------------|------|
| 单进程 `hfd` / `download_data.py` 直拉 | 4～6 小时 | 单连接、小文件多、易重复起多个进程抢带宽 |
| **并行镜像 + 官方补漏**（推荐） | **15～30 分钟** | 8 路分片 × 每路 40 线程；失败文件走官方 HF |

早期 ETA 偏短，是因为 `hfd` 日志按**瞬时峰值**估算；大量小文件时平均速度远低于峰值。

---

## 环境准备

在项目根目录配置 `.env`（参考 `.env.example`）：

```bash
# 生成任务用的 Python（需有 huggingface_hub）
MULTI_IMAGE_EVAL_PYTHON=/path/to/venv/bin/python

# 镜像（并行阶段用）
HF_ENDPOINT=https://hf-mirror.com

# Token（补漏阶段用，强烈建议）
HF_TOKEN=hf_xxxxxxxx

# 可选调参
HF_PARALLEL_SHARDS=8      # 并行分片数
HF_DOWNLOAD_WORKERS=40    # 每个分片的线程数
HF_HFD_THREADS=10         # hfd 单进程线程（最大 10）
```

> **注意**：`huggingface_hub` 在设置了 `HF_ENDPOINT` 时，部分 API 会对该数据集下载失败。补漏脚本会**自动去掉镜像**，改走官方 `huggingface.co`。

---

## 推荐：三步快速全量下载

在任意有网络的机器上：

```bash
cd ~/work/multi-image-eval
source .env
```

### 第一步：并行拉镜像（主体，最快）

```bash
bash scripts/download_dataset_fast.sh multibanana --shards 8 --workers 40
```

- 数据落到：`data/multibanana/hf_repo/`
- 日志：`logs/download_multibanana_fast/shard*.log`
- 查看进度：

```bash
du -sh data/multibanana/hf_repo
find data/multibanana/hf_repo -type f | wc -l   # 目标约 10561
tail -f logs/download_multibanana_fast/shard0.log
```

并行原理：把 10561 个文件按编号分成 8 份，每份独立进程 + 多线程 HTTP 下载（`benchmarks/multibanana/download_parallel.py`）。

### 第二步：补缺失文件（镜像 429 时必跑）

镜像高频请求会返回 **HTTP 429**，约 2000 个文件可能失败。用官方源 + Token 补齐：

```bash
nohup $MULTI_IMAGE_EVAL_PYTHON benchmarks/multibanana/download_missing.py \
  >> logs/download_multibanana_missing.log 2>&1 &

tail -f logs/download_multibanana_missing.log
```

- 只下载 `hf_repo` 里还没有的文件，支持断点续跑
- 脚本内会 `unset HF_ENDPOINT`，避免镜像干扰 `hf_hub_download`

### 第三步：生成 metadata（本地拷贝，约 1～2 分钟）

把 `hf_repo` 整理到评测目录并写 `metadata.json`：

```bash
$MULTI_IMAGE_EVAL_PYTHON benchmarks/multibanana/download_data.py --samples-per-task 0
```

成功标志：

```
[done] metadata written: 2229 items -> data/multibanana/metadata.json
```

---

## 其他下载方式（了解即可）

### Smoke 抽样（每类 N 条）

```bash
bash scripts/download_dataset.sh multibanana --smoke 2
# 或全量参数
bash scripts/download_dataset.sh multibanana --full
```

走 `download_data.py`，适合小数据量；全量 **不推荐**（太慢）。

### 单进程 hfd + 镜像（较慢但简单）

```bash
bash scripts/download_dataset_hfd.sh multibanana --threads 10
```

- 依赖 `hf-mirror.com` 的 `hfd.sh` + `wget`
- 线程最大 **10**；不要同时起多个 `hfd`，会互相抢带宽
- 日志：`logs/download_multibanana_hfd.log`

---

## 目录结构

```
data/multibanana/
├── hf_repo/          # 并行/hfd 原始拉取（HF 目录结构）
│   ├── 3_back/
│   ├── tone/
│   └── ...
├── data/             # 评测 runner 使用的整理后数据
│   ├── 3_back/
│   └── ...
└── metadata.json     # 2229 条全量索引
```

`download_data.py` 会优先从 `hf_repo/` 本地拷贝，不再走网络。

---

## 常见问题

**Q: 能不能 30 分钟内下完？**  
A: 可以。用「并行镜像 + 官方补漏」三步法；单 `hfd` 很难做到。

**Q: 为什么 `HF_ENDPOINT` 配置了反而报错？**  
A: 该数据集在镜像上**列目录可用、部分文件拉取会失败/429**。并行阶段用镜像；补漏阶段必须用 `download_missing.py`（官方源）。

**Q: 下载中断了怎么办？**  
A: 重新跑同一条命令即可，已有文件会跳过（`skip`）。

**Q: 控制台「全量」显示多少条？**  
A: 全量 **2229** 条（36 类任务）；smoke 为每类抽样。

---

## 脚本一览

| 脚本 | 用途 |
|------|------|
| `scripts/download_dataset_fast.sh` | **推荐** 多进程并行镜像下载 |
| `benchmarks/multibanana/download_missing.py` | 官方源补缺失文件 |
| `benchmarks/multibanana/download_data.py` | 整理目录 + 写 metadata |
| `scripts/download_dataset_hfd.sh` | 单进程 hfd（慢） |
| `scripts/download_dataset.sh` | 通用入口（smoke/full，偏慢） |
