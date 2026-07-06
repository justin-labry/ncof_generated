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


async def notify(sub_id: str, notif_uri: str, payload: Any):
    logger.info(f"[{sub_id}]try to send notification to {notif_uri}")
    try:
        async with httpx.AsyncClient(verify=False) as client:
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
