#!/bin/bash
export PORT=${PORT:-8004}
uv run --no-sync uvicorn nncof_cb.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --log-config "./log_config.ini" \
  --reload
