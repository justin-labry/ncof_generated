"""
Unified test server for producer + callback generated stubs.

Run:
  python test_server.py

Swagger UI:
  http://localhost:8000/docs
"""

from pathlib import Path
import json
import sys
from typing import Any

from fastapi import Body, FastAPI


ROOT = Path(__file__).resolve().parent

# Make generated packages importable without pip install.
for pkg in ("nncof", "nupf", "nnef", "nsmf", "nncof_cb", "nupf_cb", "nnef_cb", "nsmf_cb"):
    sys.path.insert(0, str(ROOT / pkg / "src"))


def _patch_generated_security_files() -> None:
    """Patch generated security_api.py so import-time NameError does not happen."""
    targets = (
        ROOT / "nncof" / "src" / "nncof" / "security_api.py",
        ROOT / "nupf" / "src" / "nupf" / "security_api.py",
        ROOT / "nnef" / "src" / "nnef" / "security_api.py",
        ROOT / "nsmf" / "src" / "nsmf" / "security_api.py",
        ROOT / "nncof_cb" / "src" / "nncof_cb" / "security_api.py",
        ROOT / "nupf_cb" / "src" / "nupf_cb" / "security_api.py",
        ROOT / "nnef_cb" / "src" / "nnef_cb" / "security_api.py",
        ROOT / "nsmf_cb" / "src" / "nsmf_cb" / "security_api.py",
    )

    marker = "oauth2_ = OAuth2PasswordBearer(tokenUrl=\"/oauth2/token\", auto_error=False)"
    anchor = "from fastapi.security.api_key import APIKeyCookie, APIKeyHeader, APIKeyQuery  # noqa: F401\n"
    inject = (
        "\n"
        "oauth2_ = OAuth2PasswordBearer(tokenUrl=\"/oauth2/token\", auto_error=False)\n"
    )

    for path in targets:
        if not path.exists():
            continue
        text = path.read_text()
        if marker in text:
            continue
        if anchor in text:
            path.write_text(text.replace(anchor, anchor + inject, 1))


_patch_generated_security_files()

from nncof.apis.ncof_events_subscriptions_collection_api import router as nncof_subs_router  # noqa: E402
from nncof.apis.ncof_event_subscription_transfers_collection_api import router as nncof_transfers_router  # noqa: E402
from nncof.apis.individual_ncof_events_subscription_document_api import router as nncof_sub_doc_router  # noqa: E402
from nncof.apis.individual_ncof_event_subscription_transfer_document_api import router as nncof_transfer_doc_router  # noqa: E402
from nupf.apis.subscriptions_collection_api import router as nupf_subs_router  # noqa: E402
from nupf.apis.default_api import router as nupf_default_router  # noqa: E402
from nnef.apis.subscriptions_collection_api import router as nnef_subs_router  # noqa: E402
from nnef.apis.individual_subscription_document_api import router as nnef_doc_router  # noqa: E402
from nsmf.apis.subscriptions_collection_api import router as nsmf_subs_router  # noqa: E402
from nsmf.apis.individual_subscription_document_api import router as nsmf_doc_router  # noqa: E402

from nncof_cb.apis.ncof_events_subscription_notification_callback_receiver_api import router as nncof_cb_router  # noqa: E402
from nupf_cb.apis.upf_event_exposure_notification_callback_receiver_api import router as nupf_cb_router  # noqa: E402
from nnef_cb.apis.nef_event_exposure_notification_callback_receiver_api import router as nnef_cb_router  # noqa: E402
from nsmf_cb.apis.smf_event_exposure_notification_callback_receiver_api import router as nsmf_cb_router  # noqa: E402


app = FastAPI(
    title="NCOF Unified Test Server",
    description="Unified server for producer APIs and callback receiver APIs.",
    version="0.1.0",
)

# Producer routers
app.include_router(nncof_subs_router, prefix="/api/nncof")
app.include_router(nncof_transfers_router, prefix="/api/nncof")
app.include_router(nncof_sub_doc_router, prefix="/api/nncof")
app.include_router(nncof_transfer_doc_router, prefix="/api/nncof")
app.include_router(nupf_subs_router, prefix="/api/nupf")
app.include_router(nupf_default_router, prefix="/api/nupf")
app.include_router(nnef_subs_router, prefix="/api/nnef")
app.include_router(nnef_doc_router, prefix="/api/nnef")
app.include_router(nsmf_subs_router, prefix="/api/nsmf")
app.include_router(nsmf_doc_router, prefix="/api/nsmf")

# Callback routers
app.include_router(nncof_cb_router, prefix="/callback/nncof")
app.include_router(nupf_cb_router, prefix="/callback/nupf")
app.include_router(nnef_cb_router, prefix="/callback/nnef")
app.include_router(nsmf_cb_router, prefix="/callback/nsmf")


def _echo_payload(name: str, data: Any) -> dict:
    """Print request payload and return it for quick manual validation."""
    print(f"\n===== {name} =====")
    try:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except TypeError:
        print(str(data))
    print("===== END =====\n")
    return {"ok": True, "endpoint": name, "received": data}


@app.post("/validate/nncof-events-subscription")
def validate_nncof_events_subscription(data: Any = Body(...)) -> dict:
    return _echo_payload("validate/nncof-events-subscription", data)


@app.post("/validate/nncof-events-subscription-notification")
def validate_nncof_events_subscription_notification(data: Any = Body(...)) -> dict:
    return _echo_payload("validate/nncof-events-subscription-notification", data)


@app.post("/validate/nupf-event-exposure-notification")
def validate_nupf_event_exposure_notification(data: Any = Body(...)) -> dict:
    return _echo_payload("validate/nupf-event-exposure-notification", data)


@app.post("/validate/nnef-event-exposure-notification")
def validate_nnef_event_exposure_notification(data: Any = Body(...)) -> dict:
    return _echo_payload("validate/nnef-event-exposure-notification", data)


@app.post("/validate/nsmf-event-exposure-notification")
def validate_nsmf_event_exposure_notification(data: Any = Body(...)) -> dict:
    return _echo_payload("validate/nsmf-event-exposure-notification", data)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

