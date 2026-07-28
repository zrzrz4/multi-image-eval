#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export MULTI_IMAGE_EVAL_ROOT="$ROOT"
export PATH="${HOME}/.nvm/versions/node/v18.20.8/bin:${PATH:-}"

bash "$ROOT/scripts/setup_viewer_venv.sh"

for APP in console eval-viewer; do
  cd "$ROOT/frontend/$APP"
  if [[ ! -d node_modules ]]; then npm install; fi
  npm run build
done

PORT="${VIEWER_PORT:-8765}"
LOG="$ROOT/logs/viewer_server.log"
mkdir -p "$ROOT/logs" "$ROOT/jobs"

if pgrep -f "$ROOT/frontend/server.py" >/dev/null 2>&1; then
  pkill -f "$ROOT/frontend/server.py" || true
  sleep 1
fi

nohup "$ROOT/.venvs/viewer/bin/python" "$ROOT/frontend/server.py" >>"$LOG" 2>&1 &
sleep 2

IP=$(hostname -I | awk '{print $1}')
echo "[platform] 控制台  http://${IP}:${PORT}/"
echo "[platform] 样例看板 http://${IP}:${PORT}/samples/"
echo "[platform] log -> $LOG"
curl -s "http://127.0.0.1:${PORT}/api/console/gpus" | python3 -m json.tool | head -20
