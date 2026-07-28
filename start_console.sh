#!/usr/bin/env bash
# 本机安装目录内的日常启动脚本（发布包内也会带一份）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
export MULTI_IMAGE_EVAL_ROOT="$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  # shellcheck source=/dev/null
  set -a; source "$ROOT/.env"; set +a
fi

bash "$ROOT/scripts/setup_viewer_venv.sh"

PORT="${VIEWER_PORT:-8765}"
LOG="$ROOT/logs/viewer_server.log"
mkdir -p "$ROOT/logs" "$ROOT/jobs" "$ROOT/outputs"

# 若发布包未含预构建 dist，且本机有 npm，则构建
export PATH="${HOME}/.nvm/versions/node/v18.20.8/bin:${PATH:-}"
if [[ ! -f "$ROOT/frontend/console/dist/index.html" ]] && command -v npm >/dev/null 2>&1; then
  for APP in console eval-viewer; do
    (cd "$ROOT/frontend/$APP" && npm install --silent && npm run build)
  done
fi

if pgrep -f "$ROOT/frontend/server.py" >/dev/null 2>&1; then
  pkill -f "$ROOT/frontend/server.py" || true
  sleep 1
fi

nohup "$ROOT/.venvs/viewer/bin/python" "$ROOT/frontend/server.py" >>"$LOG" 2>&1 &
sleep 2

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "[multi-image-eval] 控制台 http://${IP:-127.0.0.1}:${PORT}/"
echo "[multi-image-eval] log -> $LOG"
