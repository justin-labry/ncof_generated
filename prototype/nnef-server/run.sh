# 설정 단일 출처: prototype/ncof_setting.conf
# SIM_SEED 는 CLI 값(빈 값 포함)이 있으면 파일값보다 우선
_cli_sim_seed_set="${SIM_SEED+x}"; _cli_sim_seed="${SIM_SEED-}"
set -a; . "$(dirname "$0")/../ncof_setting.conf"; set +a
[ -n "$_cli_sim_seed_set" ] && export SIM_SEED="$_cli_sim_seed"
export PORT=${PORT:-$NEF_PORT}
# log_config.ini 의 file 핸들러가 쓰는 ./logs 디렉터리 확보(없으면 매 로그마다 Logging error)
mkdir -p logs
APP_MODE=NEF \
uv run --no-sync uvicorn nnef.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --log-config "../log_config.ini" \
  --reload
