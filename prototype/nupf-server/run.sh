#!/bin/bash
# 설정 단일 출처: prototype/ncof_setting.conf
set -a; . "$(dirname "$0")/../ncof_setting.conf"; set +a
uv run --no-sync uvicorn nupf.main:app --host 0.0.0.0 --port ${PORT:-$UPF_PORT}
