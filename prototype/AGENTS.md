# AGENTS.md

**Generated:** 2026-05-13

## REPO OVERVIEW

6G-I2P PoC — NCOF Event Exposure Service with NF mock servers. uv workspace monorepo.

```
ncof_impl_merge/
├── nncof-server/         # NCOF orchestrator (FastAPI, OpenAPI-generated + custom core)
├── nsmf-server/          # SMF SBI mock (FastAPI, OpenAPI-generated)
├── nnef-server/          # NEF SBI mock — dual-mode (AF / RICF) (FastAPI, OpenAPI-generated)
├── nupf-server/          # UPF Event Exposure mock (FastAPI, OpenAPI-generated)
├── nncof-ui/             # SignalViz — Vue 3 + D3.js + Tailwind v4 dashboard
├── yaml/                 # OpenAPI YAML specs + codegen scripts + converter
├── pyproject.toml         # uv workspace root (only workspace definition)
└── uv.lock
```

## WORKSPACE DEPS (tool.uv.sources)

```
nncof-server → nsmf-server, nnef-server, nupf-server
nsmf-server  → nupf-server
nnef-server  → (standalone)
nupf-server  → (standalone)
```

All published as hatchling wheel packages under `src/<package>/`.

## PORT MAP (dev via run.sh)

| Service | Port | Script |
|---------|------|--------|
| nncof-server (NCOF) | 8000 | `nncof-server/run.sh` |
| nsmf-server (SMF) | 8001 | `nsmf-server/run.sh` |
| nnef-server (AF mode) | 8002 | `nnef-server/run_af.sh` |
| nnef-server (RICF mode) | 8003 | `nnef-server/run_ricf.sh` |
| nupf-server (UPF) | 8003 | `nupf-server/run.sh` |

**Known conflict:** nupf-server and nnef RICF both default to port 8003. Run on different hosts or override PORT.

## COMMANDS

```bash
# === Python Servers (each in its own directory) ===
uv sync                               # Install all workspace deps
cd nncof-server && sh run.sh          # Start NCOF server (port 8000)
cd nsmf-server && sh run.sh           # Start SMF mock (port 8001)
cd nnef-server && sh run_af.sh        # Start NEF AF mode (port 8002)
cd nnef-server && sh run_ricf.sh      # Start NEF RICF mode (port 8003)
cd nupf-server && sh run.sh           # Start UPF mock (port 8003)

PORT=9999 sh run.sh                   # Override default port

# === Frontend (nncof-ui) ===
cd nncof-ui && npm install && npm run dev   # Dev server (proxies to localhost:8000)
cd nncof-ui && npm run build                # Build → copies to nncof-server/src/nncof/static/

# === Tests ===
cd nncof-server && PYTHONPATH=src pytest tests/   # NCOF server tests
cd nsmf-server && PYTHONPATH=src pytest tests/    # SMF tests
cd nupf-server && PYTHONPATH=src pytest tests/    # UPF tests

# === Code Generation (from YAML specs) ===
# Uses docker: openapitools/openapi-generator-cli:latest
sh yaml/generate_ncof.sh     # Regenerate nncof-server from YAML
sh yaml/generate_smf.sh      # Regenerate nsmf-server from YAML
sh yaml/generate_nef.sh      # Regenerate nnef-server from YAML
sh yaml/generate_upf.sh      # Regenerate nupf-server from YAML
```

## ARCHITECTURE

### NCOF Server (nncof-server) — the core orchestrator

**OpenAPI-generated base + custom impl pattern:** Generated `*_api_base.py` files are NEVER edited directly. Custom `*_api.py` files inherit/replace them. Business logic lives in `src/nncof/core/` (not in the API layer).

Key modules in `core/`:
- `subscription_manager.py` — Singleton. All CRUD + `normalize_subscription()`. Core entrypoint.
- `subscription_handler.py` — NF subscription requests, data collection, SubscriptionDataStore.
- `subscription_request_builder.py` — ~600 lines. NF-type branching via `_handle_*` private functions (nsmf/nnef/upf).
- `websocket_manager.py` — ConnectionManager singleton, browser dashboard real-time.
- `nrf.py` — NFDiscovery singleton, NRF service lookup.
- `supi_mapping.py` — Static JSON-based IP/SUPI mapping.

**Critical circular dependency:** `subscription_manager.py` ←→ `subscription_handler.py`. Resolved via lazy imports (`from nncof.core.subscription_manager import SubscriptionManager` inside functions).

**Security:** `src/nncof/security_api.py` — OAuth2 client credentials stub (returns empty string). PoC only — replace for production.

**Static files:** `src/nncof/static/` serves the Vue dashboard (copied from nncof-ui build). Root path `/` serves `index.html`.

### NF Mock Servers (nsmf-server, nnef-server, nupf-server)

Each is OpenAPI-generated with the same structural pattern:
- `src/<package>/apis/` — OpenAPI base routers
- `src/<package>/impl/` — Custom implementation (thin, delegates to generated)
- `src/<package>/models/` — Auto-generated Pydantic models (DO NOT EDIT)
- `src/<package>/security_api.py` — OAuth2 stub

### nnef-server — Dual Mode (special)

Uses `APP_MODE` env var to switch:
- `APP_MODE=AF` → loads `subscription_api_impl_af.py`, `subscriptions_impl_af.py`
- `APP_MODE=RICF` → loads `subscription_api_impl_ricf.py`, `subscriptions_impl_ricf.py`

### Frontend (nncof-ui)

- Vue 3 + Composition API (`<script setup>`)
- Pinia state management, D3.js visualization, Tailwind CSS v4
- Lucide icons
- Vite dev server proxies `/api`, `/subscriptions`, `/api/ws` → `localhost:8000`
- Build copies to `../nncof-server/src/nncof/static/`

## CONVENTIONS

- **Python >= 3.12** required. All server pyproject.toml files enforce this.
- **PYTHONPATH=src** mandatory when running Python servers directly (or via `uv run`).
- **한글 주석** — Korean comments in business logic. API docs and generated code comments are English.
- **Singleton by module-level instance** — SubscriptionManager, ConnectionManager, NFDiscovery all instantiated at module load.
- **Pydantic v2** — All models use Pydantic v2 (OpenAPI Generator default).
- **Hatchling build** — `[tool.hatch.build.targets.wheel] packages = ["src/<package>"]`.
- **Flake8 + setup.cfg** for linting (per-server `.flake8` and `setup.cfg`). No ruff, no mypy.
- **No CI/CD** — No GitHub Actions workflows, no pre-commit hooks.

## ANTI-PATTERNS & GOTCHAS

- **Circular imports** in nncof-server/core/ between subscription_manager and subscription_handler.
- **Global mutable state** — Singleton instances live for process lifetime. Test isolation requires manual reset.
- **Port conflict** — nupf-server and nnef RICF both default to 8003.
- **Security is a stub** — OAuth2 validation returns empty string in all servers.
- **Models dir is auto-generated** — Editing `models/` files is overwritten on regeneration.
- **nupf-server port mismatch** — README says 8080, run.sh says 8003, docker-compose says 8080.
- **Docker compose all use port 8080** — Can't run multiple containers simultaneously without changes.

## PER-SERVER AGENTS.md FILES

These files have more detailed per-package guidance:

| Package | File |
|---------|------|
| nncof-server (overall) | `nncof-server/AGENTS.md` |
| nncof-server (core) | `nncof-server/src/nncof/core/AGENTS.md` |
| nncof-server (apis) | `nncof-server/src/nncof/apis/AGENTS.md` |
| nsmf-server | `nsmf-server/AGENTS.md` |
| nupf-server | `nupf-server/AGENTS.md` |

## YAML / CODEGEN

Source OpenAPI specs live in `yaml/`:
- `Nncof_EventsSubscription_PoC_ETRI_DoDo1.yaml` — NCOF spec
- `TS29508_Nsmf_EventExposure_PoC_ETRI_DoDo1.yaml` — SMF spec
- `TS29591_Nnef_EventExposure_PoC_ETRI_DoDo1.yaml` — NEF spec
- `TS29564_Nupf_EventExposure_PoC_ETRI_DoDo1.yaml` — UPF spec
- `TS26xxx_CommonData_*.yaml` — Shared/common data types (referenced by specs)
- `yaml_converter.py` + `convert_anyof_enum.py` — Pre-processing for OpenAPI Generator compatibility
