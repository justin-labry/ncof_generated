#!/bin/bash
export PORT=${PORT:-8001}
uv run uvicorn nsmf.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --log-config "./log_config.ini" \
  --reload
