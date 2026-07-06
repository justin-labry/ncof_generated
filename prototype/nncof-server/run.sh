#!/bin/bash
export PORT=${PORT:-8000}
uv run --no-sync uvicorn nncof.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --log-config "./log_config.ini" \
    --reload
