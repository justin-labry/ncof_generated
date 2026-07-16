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


TLS_VERIFY: bool | str = False


async def notify(sub_id: str, notif_uri: str, payload: Any):
    try:
        async with httpx.AsyncClient(
            http2=True, verify=TLS_VERIFY, timeout=httpx.Timeout(5.0)
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
    app_mode = os.getenv("APP_MODE", "Callback Server(PCF, RICF)").upper()
    port = int(os.getenv("PORT", 8000))  #

    panel = Panel(
        f"Mode: {app_mode} port: {port}",
        style="bold magenta",
        title="Callback Mockup",
        expand=False,
        padding=1,
    )
    console.print(panel)
