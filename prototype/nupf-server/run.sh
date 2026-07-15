#!/bin/bash
# 포트 단일 출처: prototype/nf_ports.conf
set -a; . "$(dirname "$0")/../nf_ports.conf"; set +a
uv run --no-sync uvicorn nupf.main:app --host 0.0.0.0 --port ${PORT:-$UPF_PORT}
