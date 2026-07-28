# 新增评测方法（Benchmark）

每个 benchmark 是 `benchmarks/<id>/` 下的独立插件，平台通过 `manifest.json` 自动发现。

**目标：新 benchmark 只写「数据 + 生成/评测逻辑」，其余尽量复用 `core/` 与控制台前端。**

## 最小目录

```
benchmarks/my_bench/
├── manifest.json      # 元数据、参数 schema、产物路径、viewer 维度
├── plugin.py          # 薄封装：build_run_args + build_viewer_data + 可选 hooks
├── run.py             # 生成 + 评测（可 import core.runner.progress）
├── data_utils.py      # 本 benchmark 的数据格式
└── export_viewer.py   # 可选：组装 viewer JSON（或直接在 plugin 内调用）
```

## 平台自动提供的共用能力

| 模块 | 用途 |
|------|------|
| `core.runner.progress` | `JobProgress`、分片、`write_progress` |
| `core.runner.args` | `runner_argv_head`、`append_dataset_flags` 等 CLI 拼装 |
| `core.jobs.manager` | 多 GPU 分片、**自动注入 `--progress-file`**、取消、导出 |
| `core.jobs.viewer_data` | 样例 scope + trim + **normalize 统一字段** |
| `core.dataset.scope` | 按 `task_types` / `samples_per_task` 过滤样本 |
| `core.console.samples` | 画廊截断（每类 N 条） |
| `core.console.versions` | 版本分组（读 manifest `fingerprint.param_keys`） |
| `core.viewer.normalize` | `model_output` / `model_scores` 等稳定字段 |
| 控制台 UI | 参数表单、GPU、预热、并行进度、样例画廊 — **无需改前端** |

## manifest.json 要点

```json
{
  "paths": { "data_subdir": "my_bench", "output_subdir": "my_bench" },
  "runner": { "script": "benchmarks/my_bench/run.py" },
  "artifacts": {
    "progress_file": "progress.json",
    "progress_shard_pattern": "progress_shard{shard}.json",
    "eval_summary": "eval_summary.json"
  },
  "fingerprint": {
    "param_keys": ["dataset_mode", "samples_per_task", "num_inference_steps", ...]
  },
  "viewer": {
    "enabled": true,
    "data_file": "my_bench.json",
    "score_scale": 10,
    "samples_per_task_all": 3,
    "samples_per_task_filtered": 6,
    "dimensions": [{ "key": "score", "label": "总分" }]
  },
  "params": [ ... ]
}
```

- **`artifacts`**：job manager 据此聚合进度、读评测汇总；runner 只需写这些文件。
- **`fingerprint`**：控制「测试版本」如何按参数分组；不写则默认用全部 `params` 字段。
- **`viewer.dimensions`**：控制台样例详情里的评分维度，前端自动渲染。

## plugin.py 最少实现

```python
from core.runner.args import (
    append_dataset_flags, append_eval_flags, append_inference_flags, runner_argv_head,
)

def build_run_args(manifest, output_dir, model_path, params, py_bin):
    args = runner_argv_head(manifest, output_dir, model_path, py_bin)
    append_dataset_flags(args, params)      # 若 manifest 有 dataset_mode / task_types
    append_inference_flags(args, params)    # 若有 num_inference_steps 等
    append_eval_flags(args, params)         # 若有 eval_inline / judge_model
    return args

def build_viewer_data(manifest, job, output_dir, *, model_label):
    return build_payload(...)  # 返回 items[]，字段建议含 model_output / model_scores
```

可选 hooks（不写则跳过）：

- `get_dataset_info(manifest, params)`
- `get_console_options(manifest, params)` — 动态 multiselect 等
- `resolve_image(manifest, path)`

## run.py 约定

- 接受 `--progress-file`（manager 会自动传入，**不要硬编码进度文件名**）
- 使用 `core.runner.progress.JobProgress` 写 `gen_done` / `eval_done` / `phase`
- 评测汇总写到 manifest `artifacts.eval_summary`

## viewer 字段约定（控制台自动识别）

| 字段 | 含义 |
|------|------|
| `items[].model_output` | 生成图路径（兼容旧名 `firered`） |
| `items[].model_scores` | 分数 dict（兼容 `firered_scores`） |
| `model_avg_score` | 均分 |
| `dimensions` | `[{key, label}]`，可在 manifest.viewer 声明 |

## 添加步骤 checklist

1. `benchmarks/<id>/manifest.json`
2. `plugin.py` — `build_run_args` + `build_viewer_data`
3. `run.py` — 生成/评测
4. `data_utils.py` + 可选 `download_data.py`
5. `bash scripts/start_viewer.sh` 重启

**无需修改**：`frontend/server.py` 路由列表、`App.jsx`、版本/样例/GPU/预热组件（除非新 benchmark 有特殊 UI）。

## MultiBanana 参考

- `benchmarks/multibanana/manifest.json` — 完整 fingerprint + viewer dimensions
- `benchmarks/multibanana/plugin.py` — 薄 plugin（~30 行 build_run_args）
- `benchmarks/multibanana/run.py` — 仅 MultiBanana 特有的生成 + Gemini 裁判
