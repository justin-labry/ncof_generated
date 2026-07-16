#!/bin/bash
# 포트 단일 출처: prototype/nf_ports.conf
set -a; . "$(dirname "$0")/../nf_ports.conf"; set +a
export PORT=${PORT:-$UPF_PORT}
# 기본 h2c(평문 HTTP/2). NCOF_TLS=1 이면 HTTP/2 over TLS.
TLS_ARGS=""
case "${NCOF_TLS:-}" in 1|true|TRUE|yes|on) TLS_ARGS="--certfile ../cert.pem --keyfile ../key.pem" ;; esac
# Hypercorn으로 HTTP/2 가동
uv run --no-sync hypercorn nupf.main:app \
    --bind "0.0.0.0:$PORT" \
    $TLS_ARGS \
    --log-config "./log_config.ini"
