export PORT=${PORT:-8003}
APP_MODE=RICF \
uv run --no-sync uvicorn nnef.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --log-config "./log_config.ini" \
  --reload
