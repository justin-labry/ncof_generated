"""
Unified callback receiver server for generated *_cb packages.

Run:
  python callback_server.py

Swagger UI:
  http://localhost:8001/docs
"""

from pathlib import Path
import sys

import uvicorn
from fastapi import FastAPI


ROOT = Path(__file__).resolve().parent

# Make generated callback packages importable without pip install.
sys.path.insert(0, str(ROOT / "nncof_cb" / "src"))
sys.path.insert(0, str(ROOT / "nupf_cb" / "src"))
sys.path.insert(0, str(ROOT / "nnef_cb" / "src"))
sys.path.insert(0, str(ROOT / "nsmf_cb" / "src"))

from nncof_cb.apis.ncof_events_subscription_notification_callback_receiver_api import (  # noqa: E402
    router as nncof_router,
)
from nupf_cb.apis.upf_event_exposure_notification_callback_receiver_api import (  # noqa: E402
    router as nupf_router,
)
from nnef_cb.apis.nef_event_exposure_notification_callback_receiver_api import (  # noqa: E402
    router as nnef_router,
)
from nsmf_cb.apis.smf_event_exposure_notification_callback_receiver_api import (  # noqa: E402
    router as nsmf_router,
)


app = FastAPI(
    title="NCOF Unified Callback Receiver",
    description="Unified callback server for nncof_cb/nupf_cb/nnef_cb/nsmf_cb.",
    version="0.1.0",
)

# All generated callback routers use POST /notifications internally.
# We add prefixes to avoid path collisions in one app.
app.include_router(nncof_router, prefix="/callback/nncof")
app.include_router(nupf_router, prefix="/callback/nupf")
app.include_router(nnef_router, prefix="/callback/nnef")
app.include_router(nsmf_router, prefix="/callback/nsmf")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
