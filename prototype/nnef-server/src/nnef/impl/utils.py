import json
import os
from typing import Any
import httpx

from rich.panel import Panel
from rich.console import Console

import logging

from colorlog import ColoredFormatter

logger = logging.getLogger(__name__)

console = Console()


def load_json(filename: str) -> dict:
    json_file_path = os.path.join(os.path.dirname(__file__), filename)
    with open(json_file_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def notify(sub_id: str, notif_uri: str, payload: Any):
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


def print_logo():
    app_mode = os.getenv("APP_MODE", "None").upper()
    port = int(os.getenv("PORT", 8000))  #
    panel = Panel(
        f"Mode: {app_mode} port: {port}",
        style="bold magenta",
        title="NEF Event Exposure Mockup",
        expand=False,
        padding=1,
    )
    console.print(panel)


class ShortNameFormatter(ColoredFormatter):
    def format(self, record):
        # 마침표(.)로 구분된 이름 중 가장 마지막 요소만 추출
        # 예: 'nnef.sub.module' -> 'module'
        # 예: 'uvicorn.error' -> 'error'
        record.short_name = record.name.split(".")[-1]
        return super().format(record)
