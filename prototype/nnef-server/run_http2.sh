#!/bin/bash
# 포트 단일 출처: prototype/nf_ports.conf
set -a; . "$(dirname "$0")/../nf_ports.conf"; set +a
export PORT=${PORT:-$NEF_PORT}
export APP_MODE=NEF
# Hypercorn으로 HTTP/2 가동
uv run --no-sync hypercorn nnef.main:app \
    --bind "0.0.0.0:$PORT" \
    --certfile ../cert.pem \
    --keyfile ../key.pem \
    --log-config "./log_config.ini"
