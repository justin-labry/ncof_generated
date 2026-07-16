# 설정 단일 출처: prototype/ncof_setting.conf
set -a; . "$(dirname "$0")/../ncof_setting.conf"; set +a
export PORT=${PORT:-$NEF_PORT}
APP_MODE=NEF \
uv run --no-sync uvicorn nnef.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --log-config "./log_config.ini" \
  --reload
