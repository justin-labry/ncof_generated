import os
import logging
import time
import socket

from functools import reduce

from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)

console = Console()


def safe_get(obj, *attrs, default=None):
    """중첩 속성을 안전하게 가져옴. 중간에 None이면 default 반환."""
    try:
        return reduce(getattr, attrs, obj)
    except AttributeError:
        return default


def safe_set(target_obj, target_attrs: list, value):
    """중첩 속성을 안전하게 설정. 중간 객체가 None이면 스킵."""
    try:
        obj = reduce(getattr, target_attrs[:-1], target_obj)
        if obj is not None:
            setattr(obj, target_attrs[-1], value)
    except AttributeError:
        pass


def print_logo(title, description, version):

    port = os.getenv("PORT", 8000)

    table = Table(box=None, show_header=False, padding=(0, 2))

    table.add_column(style="dim")
    table.add_column(style="bold white")
    table.add_row("NAME", f"{title}")
    table.add_row("DESCRIPTION", f"{description}")
    table.add_row("VERSION", f"{version}")
    table.add_row("PORT", f"[bold yellow]{port}[/]")
    table.add_row("STATUS", "[bold green]● RUNNING[/]")

    panel = Panel(
        table,
        title="[bold blue]NNCOF[/]",
        title_align="left",
        subtitle_align="right",
        border_style="blue",
        box=box.DOUBLE_EDGE,
        padding=(1, 1, 1, 1),
        expand=False,
    )
    console.print(panel)


def get_current_timestamp():
    """현재 시간을 밀리초(ms) 단위의 타임스탬프로 반환"""
    return int(time.time() * 1000)


def _get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def system_info():
    port = int(os.getenv("PORT", 8000))
    description = os.getenv(
        "APP_DESCRIPTION", "NCOF Event Exposure Service for 6G-I2P PoC Scenario."
    )
    version = os.getenv("APP_VERSION", "0.1.0")
    title = os.getenv("APP_TITLE", "Nncof_EventsSubscription")
    ip = _get_local_ip()
    return {
        "status": "online",
        "title": title,
        "description": description,
        "version": version,
        "port": port,
        "ip": ip,
        "notification_base_uri": f"http://{ip}:{port}/notifications",
    }
