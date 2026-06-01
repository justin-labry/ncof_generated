from functools import reduce
import json
import os
from typing import Any
import httpx
from rich.panel import Panel
from rich.console import Console
from rich.logging import RichHandler
import logging
import yaml
import logging.config

logger = logging.getLogger(__name__)
console = Console()

from rich.table import Table
from rich import box


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

    port = int(os.getenv("PORT", 8000))  #

    table = Table(box=None, show_header=False, padding=(0, 2))

    table.add_column(style="dim")
    table.add_column(style="bold white")
    table.add_row("NAME", f"{title}")
    table.add_row("DESCRIPTION", f"{description}")
    table.add_row("VERSION", f"{version}")

    table.add_row("PORT", f"[bold yellow]{str(port)}[/]")
    table.add_row("STATUS", "[bold green]● RUNNING[/]")

    panel = Panel(
        table,
        title="[bold cyan]NNCOF[/]",
        title_align="left",
        subtitle="[dim]ctrl+c to stop[/]",
        subtitle_align="right",
        border_style="cyan",
        box=box.DOUBLE_EDGE,
        padding=(0, 1),
        expand=False,
    )
    console.print(panel)


# def setup_logging(config_path="logging_config.yaml"):
#     # 현재 파일의 디렉토리를 기준으로 config 파일 경로 설정
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     config_path = os.path.join(script_dir, config_path)

#     if not os.path.exists(config_path):
#         print(f"WARNING: Logging config file not found at {config_path}")
#         # 기본 로깅 설정
#         logging.basicConfig(
#             level=logging.INFO,
#             format="[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s [%(filename)s:%(lineno)d]",
#         )
#         return

#     try:
#         with open(config_path, "r", encoding="utf-8") as f:
#             config = yaml.safe_load(f)

#         # 커스텀 필터 클래스 (logging_config.yaml의 'path.to.your.ShortNameFilter'에 해당)
#         class ShortNameFilter(logging.Filter):
#             def filter(self, record):
#                 # 파일 이름에서 마지막 부분만 추출
#                 record.short_name = record.name.split(".")[-1]
#                 return True

#         # 필터 등록
#         config["filters"]["short_name"]["()"] = ShortNameFilter

#         # logging.config.dictConfig 사용
#         logging.config.dictConfig(config)

#         print(f"Logging configured successfully from {config_path}")

#     except Exception as e:
#         print(f"ERROR: Failed to load logging config: {e}")
#         # 오류 시 기본 설정
#         logging.basicConfig(
#             level=logging.INFO,
#             format="[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s [%(filename)s:%(lineno)d]",
#         )


def get_current_timestamp():
    """현재 시간을 밀리초(ms) 단위의 타임스탬프로 반환"""
    import time

    return int(time.time() * 1000)
