# 포트 단일 출처: prototype/nf_ports.conf (RICF 도 NEF 서버 포트를 공유)
set -a; . "$(dirname "$0")/../nf_ports.conf"; set +a
export PORT=${PORT:-$NEF_PORT}
APP_MODE=RICF \
uv run --no-sync uvicorn nnef.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --log-config "./log_config.ini" \
  --reload
