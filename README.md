# Multi-Image Eval

多图生图评测独立项目，可部署在任意 GPU 节点。

详细 GitHub 发布说明见 [docs/GITHUB.md](docs/GITHUB.md)。

## 功能

| 页面 | 地址 | 说明 |
|------|------|------|
| **控制台** | `http://<host>:8765/` | 选权重、选评测、选 GPU、填参数、提交任务 |
| **样例看板** | `http://<host>:8765/samples/` | 只读展示已发布的评测样例 |

## 目录

```
~/work/multi-image-eval/
├── core/                 # 平台共用：路径、任务、GPU、注册表
├── config/
│   └── models.json       # 模型权重（所有 benchmark 共用）
├── benchmarks/           # 各评测插件（manifest.json 自动发现）
│   └── multibanana/
├── frontend/
│   ├── console/          # 任务提交前端
│   ├── eval-viewer/      # 样例展示前端
│   └── server.py         # 统一 API
├── data/<benchmark_id>/  # 数据集
├── outputs/<benchmark_id>/
├── jobs/                 # 任务元数据
└── scripts/
```

详见 [benchmarks/README.md](benchmarks/README.md) 了解如何新增评测方法。

HuggingFace 数据集/模型加速下载（国内镜像 + 并行）：[docs/dataset-download-fast.md](docs/dataset-download-fast.md)

## 快速开始

```bash
cd ~/work/multi-image-eval
cp .env.example .env   # 填写 GEMINI_API_KEY 等

# 启动平台（构建两个前端 + API）
bash scripts/start_viewer.sh
```

## 提交任务流程

1. 打开控制台 `/`
2. 选择模型权重（`config/models.json` 可增删）
3. 选择评测类型（`benchmarks/*/manifest.json` 自动注册）
4. 勾选 GPU
5. 调整参数 → **启动评测**
6. 任务完成后点 **发布到样例看板**
7. 在 `/samples/` 查看结果

## 数据集下载

详见 [docs/dataset-download-fast.md](docs/dataset-download-fast.md)（HF 镜像 + 并行加速，通用方法）。

```bash
# 本仓库 MultiBanana 全量
bash scripts/download_dataset_fast.sh multibanana --shards 8 --workers 40
```

## 环境

- 看板：`.venvs/viewer`（FastAPI）
- 生成：`.venvs/gen`（需自行安装 torch/diffusers，见 `requirements.txt`）
- 或通过环境变量 `MULTI_IMAGE_EVAL_PYTHON` 指定 Python 路径

## 新增评测类型

在 `benchmarks/<name>/` 添加 `manifest.json`、`plugin.py`、`run.py` 等，无需改中央配置文件。步骤见 [benchmarks/README.md](benchmarks/README.md)。
