export PORT=${PORT:-8002}
APP_MODE=AF \
uv run uvicorn nnef.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --log-config "./log_config.ini" \
  --reload
