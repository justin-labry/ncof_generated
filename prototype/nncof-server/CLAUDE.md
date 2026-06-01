# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI server generated from an OpenAPI specification for the NCOF (Nncof_EventsSubscription) Event Exposure Service. It's designed for a 6G-I2P PoC (Proof of Concept) scenario and provides APIs for managing event subscriptions.

The project structure follows a typical FastAPI project layout with:
- `src/` directory containing the application code
- API endpoints defined in `src/nncof/apis/`
- Data models in `src/nncof/models/`
- Security handling in `src/nncof/security_api.py`

## Development Setup

### Prerequisites
- Python >= 3.12
- pip package manager

### Installation
To run the server, please execute the following from the root directory:

```bash
pip3 install -r requirements.txt
PYTHONPATH=src uvicorn nncof.main:app --host 0.0.0.0 --port 8080
```

Or with the newer uv approach:
```bash
uv init .
uv add fastapi
uv add uvicorn
export PYTHONPATH=src
uv run uvicorn nncof.main:app --host 0.0.0.0 --port 8080
```

### Running with Docker
```bash
docker compose up --build
```

### Running Tests
```bash
pip3 install pytest
PYTHONPATH=src pytest tests
```

## Key Components

### Main Application
- `src/nncof/main.py` - The main FastAPI application with all routes included

### API Endpoints
The service exposes 4 main API collections:
1. Individual NCOF Event Subscription Transfer Document API
2. Individual NCOF Events Subscription Document API
3. NCOF Event Subscription Transfers Collection API
4. NCOF Events Subscriptions Collection API

### Data Models
The project contains numerous data models for various NCOF event types, including:
- Event subscription models
- Notification models
- Location information models
- Failure event information models
- Consumer NF information models

### Security
Security is handled via OAuth2 client credentials in `src/nncof/security_api.py` with token validation functions.

## Common Development Tasks

1. **Adding new API endpoints**: Create new API files in `src/nncof/apis/` and include them in `main.py`
2. **Modifying data models**: Edit files in `src/nncof/models/` and regenerate if needed
3. **Updating security**: Modify `src/nncof/security_api.py` for authentication/authorization changes
4. **Testing**: Run tests using `pytest` with `PYTHONPATH=src`

## Architecture Notes

This is an OpenAPI-generated FastAPI server that provides a RESTful API for NCOF event subscription management. The architecture follows standard FastAPI patterns with:
- API routers for different resource collections
- Pydantic models for data validation
- Security middleware for authentication
- Standard HTTP status codes and error handling