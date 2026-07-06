# nupf-server AGENTS.md

This is an OpenAPI-generated FastAPI server for UPF Event Exposure Service.

## Key Commands

- Run server: `export PYTHONPATH=src && uvicorn nupf.main:app --host 0.0.0.0 --port 8082`
- Run tests: `pip3 install pytest && PYTHONPATH=src pytest tests`
- Build with Docker: `docker compose up --build`

## Architecture

- Generated from OpenAPI spec (version 1.2.0-alpha.4)
- Main entrypoint: `src/nupf/main.py`
- API routers: `src/nupf/apis/` 
- Generated models: `src/nupf/models/`
- Test setup in `tests/` with `conftest.py` for TestClient fixture

## Framework Notes

- Framework: FastAPI with uvicorn
- Generated code: This is an OpenAPI-generated server (OpenAPI Generator version 7.17.0)
- Environment: Requires Python 3.7+
- Project layout: Python package structure under `src/nupf/`

## Testing

- Tests use pytest with TestClient
- Test fixtures in `tests/conftest.py`
- Test coverage across API endpoints in `tests/test_*.py`
- Note: Tests often have commented-out code that needs uncommented to run

## Deployment

- Can run via direct uvicorn command
- Docker support via docker-compose configuration
- Port 8080 by default in Docker container