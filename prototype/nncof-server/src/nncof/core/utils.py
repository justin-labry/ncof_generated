import os
import logging
import time
import socket

from functools import reduce

from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from rich import box


from typing import Any, Dict, List

from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc

from nncof.models.nncof_events_subscription import NncofEventsSubscription

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
    # 기본 h2c(평문 HTTP/2, http). NCOF_TLS 설정 시 HTTP/2 over TLS(https).
    scheme = "https" if os.getenv("NCOF_TLS", "").strip().lower() in ("1", "true", "yes", "on") else "http"
    return {
        "status": "online",
        "title": title,
        "description": description,
        "version": version,
        "port": port,
        "ip": ip,
        "notification_base_uri": f"{scheme}://{ip}:{port}/notifications",
    }


def _normalize_subscription(
    subscription: Any,
    subscription_id: str | None,
) -> Dict[str, Any]:
    """
    NncofEventsSubscription / NsmfEventExposure / NefEventExposureSubsc 세 타입의
    구독 객체를 공통 구조의 dict로 변환한다.

    Args:
        subscription: 변환할 구독 객체.
        subscription_id: SubscriptionManager 의 키로 사용되는 구독 ID.

    Returns:
        {
            "subscriptionId": str,
            "notifUri": str,
            "eventReq": {
                "notificationMethod": str (기본값 "PERIODIC"),
                "repPeriod": int (기본값 60),
            },
            "eventSubscriptions": [{ "event": str }, ...]
        }
    """
    sub_id = subscription_id if subscription_id else ""
    if isinstance(subscription, NsmfEventExposure):
        sub_id = subscription.sub_id or subscription_id

    notif_uri = ""
    if isinstance(subscription, NncofEventsSubscription):
        notif_uri = subscription.notification_uri or ""
    elif isinstance(subscription, NsmfEventExposure):
        notif_uri = subscription.notif_uri or ""
    elif isinstance(subscription, NefEventExposureSubsc):
        notif_uri = subscription.notif_uri or ""

    notif_method = "PERIODIC"
    rep_period = 60
    from_node = ""
    if isinstance(subscription, NncofEventsSubscription):
        if subscription.evt_req is not None:
            notif_method = subscription.evt_req.notif_method or notif_method
            rep_period = subscription.evt_req.rep_period or rep_period
            nf_id = (
                subscription.cons_nf_info.nf_id
                if subscription.cons_nf_info and subscription.cons_nf_info.nf_id
                else ""
            )

            # nf_id = subscription_request.cons_nf_info.nf_id
            if nf_id.startswith("pcf"):
                from_node = "pcf"
            elif nf_id.startswith("ricf"):
                from_node = "ricf"
            else:
                from_node = "unknown"

    elif isinstance(subscription, NsmfEventExposure):
        notif_method = subscription.notif_method or notif_method
        rep_period = subscription.rep_period or rep_period
    elif isinstance(subscription, NefEventExposureSubsc):
        if subscription.events_rep_info is not None:
            notif_method = subscription.events_rep_info.notif_method or notif_method
            rep_period = subscription.events_rep_info.rep_period or rep_period

    event_subs: List[Dict[str, str]] = []

    if isinstance(subscription, NncofEventsSubscription):
        if subscription.event_subscriptions:
            for es in subscription.event_subscriptions:
                event_subs.append({"event": es.event})
    elif isinstance(subscription, NsmfEventExposure):
        if subscription.event_subs:
            for es in subscription.event_subs:
                event_subs.append({"event": es.event})
    elif isinstance(subscription, NefEventExposureSubsc):
        if subscription.events_subs:
            for es in subscription.events_subs:
                event_subs.append({"event": es.event})

    return {
        "subscriptionId": sub_id,
        "notifUri": notif_uri,
        "fromNode": from_node,
        "eventReq": {
            "notificationMethod": notif_method,
            "repPeriod": rep_period,
        },
        # "eventSubscriptions": event_subs,
        "data": subscription,
    }
