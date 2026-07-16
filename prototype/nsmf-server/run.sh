#!/bin/bash
# 설정 단일 출처: prototype/ncof_setting.conf
set -a; . "$(dirname "$0")/../ncof_setting.conf"; set +a
export PORT=${PORT:-$SMF_PORT}
uv run --no-sync uvicorn nsmf.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --log-config "./log_config.ini" \
  --reload
