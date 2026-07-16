import json
import os
from typing import Any
import httpx
from rich.panel import Panel
from rich.console import Console
import logging

from rich.table import Table

logger = logging.getLogger(__name__)

console = Console()


def load_json(filename: str) -> dict:
    json_file_path = os.path.join(os.path.dirname(__file__), filename)
    with open(json_file_path, "r", encoding="utf-8") as f:
        return json.load(f)


_TLS_ENABLED = os.getenv("NCOF_TLS", "").strip().lower() in ("1", "true", "yes", "on")


def _httpx_kwargs() -> dict:
    """NCOF_TLS 설정 시 HTTP/2 over TLS(self-signed 허용), 기본은 h2c(평문 HTTP/2).
    평문 h2c 는 http1=False 로 prior-knowledge 를 강제해야 한다."""
    return {"http2": True, "verify": False} if _TLS_ENABLED else {"http1": False, "http2": True}


async def notify(sub_id: str, notif_uri: str, payload: Any):
    logger.info(f"[{sub_id}]try to send notification to {notif_uri}")
    try:
        async with httpx.AsyncClient(
            **_httpx_kwargs(), timeout=httpx.Timeout(5.0)
        ) as client:
            resp = await client.post(
                notif_uri,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )
            logger.info(f"[{sub_id}] Response: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"[{sub_id}] Notification failed: {e}")


from rich import box


def print_logo():
    app_mode = os.getenv("APP_MODE", "SMF & UPF").upper()
    port = int(os.getenv("PORT", 8000))  #

    panel = Panel(
        f"Mode: {app_mode} port: {port}",
        style="bold magenta",
        title="SMF Mockup",
        expand=False,
        padding=1,
    )
    console.print(panel)
