#!/bin/bash
# 설정 단일 출처: prototype/ncof_setting.conf (CLI 환경변수가 파일값보다 우선)
_cli_tls="${NCOF_TLS-}"
set -a; . "$(dirname "$0")/../ncof_setting.conf"; set +a
[ -n "$_cli_tls" ] && export NCOF_TLS="$_cli_tls"
export PORT=${PORT:-$PCF_PORT}

# 기본 h2c(평문 HTTP/2). NCOF_TLS=1 이면 HTTP/2 over TLS.
TLS_ARGS=""
case "${NCOF_TLS:-}" in 1|true|TRUE|yes|on) TLS_ARGS="--certfile ../cert.pem --keyfile ../key.pem" ;; esac
# Hypercorn으로 HTTP/2 가동
uv run --no-sync hypercorn nncof_cb.main:app \
    --bind "0.0.0.0:$PORT" \
    $TLS_ARGS \
    --log-config "./log_config.ini"
