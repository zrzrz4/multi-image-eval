# 发布到 GitHub

本仓库仅包含**代码与文档**，不含密钥、`.env`、任务数据、生成结果。

## 首次配置（克隆后）

```bash
cp .env.example .env
cp config/models.json.example config/models.json   # 若 models.json 不存在

# 编辑 .env（本地文件，勿提交）
#   GEMINI_API_KEY=...
#   GEMINI_BASE_URL=...    # 你的 OpenAI 兼容网关
#   GEMINI_MODEL=...
#   FIRERED_MODEL_PATH=/path/to/your/model

# 编辑 config/models.json 中的权重路径

bash scripts/setup_viewer_venv.sh
export PATH="$HOME/.nvm/versions/node/v18.20.8/bin:$PATH"   # 或本机 node
cd frontend/console && npm install && npm run build
cd ../eval-viewer && npm install && npm run build
cd ../..
bash start_console.sh
```

## 不要提交的内容

| 类型 | 说明 |
|------|------|
| `.env` | API Key、Base URL、内网路径 |
| `jobs/` `outputs/` `logs/` `data/` | 运行产物 |
| `node_modules/` `.venvs/` | 依赖与虚拟环境 |
| `config/custom_weights.json` | 本机注册的权重 |

`.gitignore` 已默认忽略上述路径。

## 打包检查（维护者）

```bash
bash scripts/package_for_github.sh
```

会在 `dist-github/` 生成干净目录，并在项目上级目录输出 `multi-image-eval-github.tar.gz`。脚本会扫描常见敏感模式，命中则失败。

## 推送到 GitHub

```bash
cd /path/to/multi-image-eval
git init
git add .
git status   # 确认无 .env / data / outputs
git commit -m "Initial public release: multi-image eval platform"
git remote add origin git@github.com:<user>/<repo>.git
git branch -M main
git push -u origin main
```

## Edit-Compass Part5（可选 benchmark）

需单独准备 [Edit-Compass](https://github.com/) 数据与 `pipeline_runner`，并设置：

```bash
export EDIT_COMPASS_ROOT=/path/to/Edit-Compass\ Part5
```

或在 `benchmarks/edit_compass_part5/manifest.json` 的 `paths` 中填写 `data_root` / `project_root`（勿将含密钥的配置提交到 Git）。

## 公共结果归档（可选）

```bash
export MIE_PUBLIC_RESULTS=/path/to/shared/results
# 或 MIE_PUBLIC_RESULTS_DEFAULT=...  # 只读归档默认根目录
```
