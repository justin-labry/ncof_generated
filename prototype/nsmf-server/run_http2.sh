#!/bin/bash
export PORT=${PORT:-8001}
# Hypercorn으로 HTTP/2 가동
uv run --no-sync hypercorn nsmf.main:app \
    --bind "0.0.0.0:$PORT" \
    --certfile ../cert.pem \
    --keyfile ../key.pem \
    --log-config "./log_config.ini" \
    --reload
