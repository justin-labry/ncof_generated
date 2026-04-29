"""
NCOF JSON Validation Test Server
- Swagger UI: http://localhost:8000/docs
- Validates all 12 NCOF JSON payloads against generated Pydantic models
- Returns detailed validation errors as JSON response
"""
import json
import warnings
import traceback
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

# Suppress ALL Pydantic serializer warnings (anyOf/oneOf Literal field noise)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nncof.models.nncof_events_subscription_notification import NncofEventsSubscriptionNotification
from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nupf.models.notification_data import NotificationData
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from nnef.models.nef_event_exposure_notif import NefEventExposureNotif

# Rebuild all models so Union[str, AnyOfClass] type changes take effect
import importlib, pkgutil
from pydantic import BaseModel

# First pass: import all modules
all_models = []
for pkg_name in ["nncof.models", "nsmf.models", "nupf.models", "nnef.models"]:
    try:
        pkg = importlib.import_module(pkg_name)
    except ImportError:
        continue
    for _, modname, _ in pkgutil.iter_modules(pkg.__path__):
        try:
            mod = importlib.import_module(f"{pkg_name}.{modname}")
            for attr in dir(mod):
                cls = getattr(mod, attr)
                if isinstance(cls, type) and issubclass(cls, BaseModel) and cls is not BaseModel:
                    all_models.append(cls)
        except Exception:
            continue

# Second pass: rebuild all (may need multiple rounds for cross-dependencies)
failed = set()
for round_num in range(5):
    for cls in all_models:
        try:
            cls.model_rebuild(force=True)
            failed.discard(cls.__name__)
        except Exception as e:
            failed.add(cls.__name__)

if failed:
    print(f"Warning: {len(failed)} models failed rebuild: {list(failed)[:10]}...")

app = FastAPI(
    title="NCOF JSON Validation Server",
    description="Validate NCOF JSON payloads against OpenAPI-generated Pydantic models.",
    version="0.1.0",
)


def pretty_json(obj, status_code=200):
    """Return a Response with indented JSON."""
    from datetime import datetime, date
    def default_serializer(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
    return Response(
        content=json.dumps(obj, indent=2, ensure_ascii=False, default=default_serializer) + "\n",
        media_type="application/json",
        status_code=status_code,
    )


def validate_and_respond(model_class, data: dict):
    """Validate using from_dict (handles anyOf enums correctly). Return pretty JSON."""
    from datetime import datetime, date
    def _default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)

    try:
        result = model_class.from_dict(data)
        # Try multiple serialization methods, use first non-empty result
        result_data = result.to_dict()
        if not result_data:
            try:
                result_data = result.model_dump(by_alias=True, exclude_none=True)
            except Exception:
                pass
        if not result_data:
            # Fallback: return original input (validation passed, just serialization issue)
            result_data = data
        resp = {"status": "PASS", "data": result_data}
        # Print pretty JSON to server console
        print("\n" + "=" * 60)
        print(f"[PASS] {model_class.__name__}")
        print("=" * 60)
        print(json.dumps(resp, indent=2, ensure_ascii=False, default=_default))
        print("=" * 60 + "\n")
        return pretty_json(resp)
    except ValidationError as e:
        unique = []
        seen = set()
        for err in e.errors():
            field = ".".join(str(x) for x in err["loc"])
            key = (field, err["msg"])
            if key not in seen:
                seen.add(key)
                unique.append({
                    "field": field,
                    "msg": err["msg"],
                    "type": err["type"],
                    "input": str(err.get("input", ""))[:200],
                })
        resp = {
            "status": "FAIL",
            "total_errors": len(e.errors()),
            "unique_errors": len(unique),
            "errors": unique,
        }
        print("\n" + "=" * 60)
        print(f"[FAIL] {model_class.__name__} - {len(unique)} unique errors")
        print("=" * 60)
        print(json.dumps(resp, indent=2, ensure_ascii=False, default=_default))
        print("=" * 60 + "\n")
        return pretty_json(resp, status_code=422)
    except Exception as e:
        resp = {
            "status": "FAIL",
            "exception": str(e)[:1000],
        }
        print("\n" + "=" * 60)
        print(f"[ERROR] {model_class.__name__}")
        print("=" * 60)
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        print("=" * 60 + "\n")
        return pretty_json(resp, status_code=422)


@app.post("/validate/nncof-events-subscription",
    tags=["1,2 - NncofEventsSubscription"],
    summary="JSON #1,2: NncofEventsSubscription (PCF/RICF -> NCOF)")
async def validate_nncof_events_subscription(data: dict = Body(...)):
    return validate_and_respond(NncofEventsSubscription, data)


@app.post("/validate/nsmf-event-exposure",
    tags=["3,7 - NsmfEventExposure"],
    summary="JSON #3,7: NsmfEventExposure (NCOF -> UPF)")
async def validate_nsmf_event_exposure(data: dict = Body(...)):
    return validate_and_respond(NsmfEventExposure, data)


@app.post("/validate/nef-event-exposure-subsc",
    tags=["4,5,6 - NefEventExposureSubsc"],
    summary="JSON #4,5,6: NefEventExposureSubsc (NCOF -> AF/RICF)")
async def validate_nef_event_exposure_subsc(data: dict = Body(...)):
    return validate_and_respond(NefEventExposureSubsc, data)


@app.post("/validate/notification-data",
    tags=["8 - NotificationData"],
    summary="JSON #8: NotificationData (UPF -> NCOF)")
async def validate_notification_data(data: dict = Body(...)):
    return validate_and_respond(NotificationData, data)


@app.post("/validate/nef-event-exposure-notif",
    tags=["9,10 - NefEventExposureNotif"],
    summary="JSON #9,10: NefEventExposureNotif (AF/RICF -> NCOF)")
async def validate_nef_event_exposure_notif(data: dict = Body(...)):
    return validate_and_respond(NefEventExposureNotif, data)


@app.post("/validate/nncof-events-subscription-notification",
    tags=["11,12 - NncofEventsSubscriptionNotification"],
    summary="JSON #11,12: NncofEventsSubscriptionNotification (NCOF -> PCF/RICF)")
async def validate_nncof_notification(data: dict = Body(...)):
    return validate_and_respond(NncofEventsSubscriptionNotification, data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
