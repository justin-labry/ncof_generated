# 하위 NF 구독 해지 시 관계 정리를 검증하는 테스트

import asyncio

from nncof.core import subscription_handler
from nncof.core.subscription_handler import SubscriptionHandler


class _Response:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _Client:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.deleted_urls: list[str] = []

    async def delete(self, url: str):
        self.deleted_urls.append(url)
        return _Response(self.status_code)


class _RelationManager:
    def __init__(self):
        self.removed_sub_ids: list[str] = []

    async def remove_relations_by_sub_id(self, sub_id: str):
        self.removed_sub_ids.append(sub_id)


def _handler_for_unsubscription(status_code: int) -> SubscriptionHandler:
    handler = object.__new__(SubscriptionHandler)
    handler.subscription_id = "ncof-subscription"
    handler._client = _Client(status_code)
    handler._relation_manager = _RelationManager()
    return handler


def test_successful_external_unsubscription_removes_its_relations(monkeypatch):
    handler = _handler_for_unsubscription(204)
    monkeypatch.setattr(subscription_handler.nrf, "get_nf_uri", lambda _: "http://nf")

    success = asyncio.run(
        handler._send_external_unsubscription("smf", "external-subscription")
    )

    assert success is True
    assert handler._client.deleted_urls == ["http://nf/subscriptions/external-subscription"]
    assert handler._relation_manager.removed_sub_ids == ["external-subscription"]


def test_missing_external_subscription_removes_stale_relations(monkeypatch):
    handler = _handler_for_unsubscription(404)
    monkeypatch.setattr(subscription_handler.nrf, "get_nf_uri", lambda _: "http://nf")

    success = asyncio.run(
        handler._send_external_unsubscription("smf", "external-subscription")
    )

    assert success is True
    assert handler._relation_manager.removed_sub_ids == ["external-subscription"]


# ---------------------------------------------------------------------------
# 하위 구독 ID 획득 — 응답에 ID 가 없는 NF(두두원 장비)를 위한 notifId 폴백
# ---------------------------------------------------------------------------


class _PostResponse:
    def __init__(self, status_code: int, body=None, headers=None):
        self.status_code = status_code
        self._body = {} if body is None else body
        self.headers = {} if headers is None else headers

    def json(self):
        return self._body


class _PostClient:
    def __init__(self, response):
        self._response = response
        self.posted_urls: list[str] = []

    async def post(self, url: str, json=None):
        self.posted_urls.append(url)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _ReqBody:
    """하위 구독 요청 본문 대역 — notifId 만 있으면 폴백 검증에 충분하다."""

    def __init__(self, notif_id):
        self.notif_id = notif_id


def _handler_for_subscription(response) -> SubscriptionHandler:
    handler = object.__new__(SubscriptionHandler)
    handler.subscription_id = "ncof-subscription"
    handler._client = _PostClient(response)
    handler._relation_manager = _RelationManager()
    return handler


_DEVICE_NOTIF_ID = "NOTIFICATION_upf_2026-09-09T19:17:29.044648+09:00"


def _subscribe(handler, notif_id=_DEVICE_NOTIF_ID):
    return asyncio.run(handler._send_external_subscription("smf", _ReqBody(notif_id)))


def test_response_without_id_falls_back_to_request_notif_id(monkeypatch):
    """두두원 장비: 200 + {"result":"ok"} — 본문·헤더 어디에도 ID 가 없다."""
    handler = _handler_for_subscription(_PostResponse(200, {"result": "ok"}))
    monkeypatch.setattr(subscription_handler.nrf, "get_nf_uri", lambda _: "http://nf")

    assert _subscribe(handler) == _DEVICE_NOTIF_ID


def test_subscription_id_header_wins_over_request_notif_id(monkeypatch):
    """ID 를 주는 NF(mock AF/RICF)에는 폴백이 도달하지 않아야 한다."""
    handler = _handler_for_subscription(
        _PostResponse(201, {}, {"Subscription-ID": "nf-issued-uuid4"})
    )
    monkeypatch.setattr(subscription_handler.nrf, "get_nf_uri", lambda _: "http://nf")

    assert _subscribe(handler) == "nf-issued-uuid4"


def test_body_sub_id_wins_over_request_notif_id(monkeypatch):
    """mock SMF: 본문 subId 가 있으면 그것을 쓴다."""
    handler = _handler_for_subscription(_PostResponse(201, {"subId": "nf-issued-subid"}))
    monkeypatch.setattr(subscription_handler.nrf, "get_nf_uri", lambda _: "http://nf")

    assert _subscribe(handler) == "nf-issued-subid"


def test_missing_notif_id_yields_no_phantom_id(monkeypatch):
    """응답에도 요청 본문에도 ID 가 없으면 유령 레코드를 만들지 않는다."""
    handler = _handler_for_subscription(_PostResponse(200, {"result": "ok"}))
    monkeypatch.setattr(subscription_handler.nrf, "get_nf_uri", lambda _: "http://nf")

    assert _subscribe(handler, notif_id="") is None
    assert _subscribe(handler, notif_id=None) is None


def test_failed_status_does_not_adopt_notif_id(monkeypatch):
    """400 등 비-2xx 응답에는 폴백이 발동하지 않는다 — 구독 자체가 실패했다."""
    handler = _handler_for_subscription(_PostResponse(400, {"error": "bad request"}))
    monkeypatch.setattr(subscription_handler.nrf, "get_nf_uri", lambda _: "http://nf")

    assert _subscribe(handler) is None


def test_connection_error_does_not_adopt_notif_id(monkeypatch):
    """연결 실패에도 폴백이 발동하면 안 된다 — 존재하지 않는 구독을 기록하게 된다."""
    handler = _handler_for_subscription(subscription_handler.httpx.RequestError("boom"))
    monkeypatch.setattr(subscription_handler.nrf, "get_nf_uri", lambda _: "http://nf")

    assert _subscribe(handler) is None


def test_unsubscription_url_keeps_notif_id_verbatim(monkeypatch):
    """해지 URL 은 ':' 와 '+' 를 percent-encoding 하지 않아야 한다.

    두두원은 경로 마지막 세그먼트를 원문 그대로 잘라 보관된 notif_id 와
    문자열 비교하므로(ncof_flow_subscription_core.cpp:1112-1137),
    quote() 를 씌우면 '%3A' 가 남아 404 로 조용히 실패한다.
    """
    handler = _handler_for_unsubscription(204)
    monkeypatch.setattr(subscription_handler.nrf, "get_nf_uri", lambda _: "http://nf")

    asyncio.run(handler._send_external_unsubscription("smf", _DEVICE_NOTIF_ID))

    assert handler._client.deleted_urls == [
        f"http://nf/subscriptions/{_DEVICE_NOTIF_ID}"
    ]
    assert "%3A" not in handler._client.deleted_urls[0]
    assert "%2B" not in handler._client.deleted_urls[0]


# --- 제어 전송 응답 처리 (순차 제어의 「앞 요청 200 확인」 근거 — 10/27 두두원: 14_e UDP 실패 · 15f 실패는 500) ---


class _ControlResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.url = "http://dodo1/"
        self.reason_phrase = "Internal Server Error" if status_code == 500 else "OK"
        self.text = text


class _ControlClient:
    def __init__(self, outcome):
        self.outcome = outcome
        self.posted: list = []

    async def post(self, url: str, json=None):
        self.posted.append((url, json))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _ControlSubscription:
    notification_uri = "http://dodo1/"


def _handler_for_control(outcome) -> SubscriptionHandler:
    handler = object.__new__(SubscriptionHandler)
    handler.subscription_id = "ncof-subscription"
    handler.subscription = _ControlSubscription()
    handler._client = _ControlClient(outcome)
    handler._on_state_change = None
    return handler


def test_control_success_returns_without_waiting_for_dashboard(monkeypatch):
    """200 직후 True — 대시보드 연출(브로드캐스트 · RICF 0.5초 대기)이 막혀 있어도 다음 제어를 붙잡지 않는다."""
    drawn: list = []
    never = asyncio.Event()

    async def stuck_broadcast(**kwargs):
        drawn.append((kwargs["from_node"], kwargs["to_node"]))
        await never.wait()

    monkeypatch.setattr(subscription_handler, "broadcast_web_message", stuck_broadcast)
    handler = _handler_for_control(_ControlResponse(200, '{"result":"ok"}'))

    async def run():
        ok = await asyncio.wait_for(handler._notify_subscriber("ricf", [{"x": 1}]), timeout=1.0)
        await asyncio.sleep(0)
        pending = list(subscription_handler._dashboard_tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        return ok

    assert asyncio.run(run()) is True
    assert handler._client.posted == [("http://dodo1/", [{"x": 1}])]
    assert drawn == [("ncof", "nef")]  # 연출은 따로 돌기 시작했다
    assert not subscription_handler._dashboard_tasks


def test_control_500_is_failure_and_logs_the_body(caplog):
    handler = _handler_for_control(_ControlResponse(500, '{"error":"internal server error"}'))

    with caplog.at_level("WARNING"):
        assert asyncio.run(handler._notify_subscriber("pcf", [{"x": 1}])) is False
    assert "status_code: 500" in caplog.text
    assert '{"error":"internal server error"}' in caplog.text


def test_control_connection_error_or_timeout_is_failure():
    for error in (
        subscription_handler.httpx.ConnectError("refused"),
        subscription_handler.httpx.ReadTimeout("5s"),
    ):
        handler = _handler_for_control(error)
        assert asyncio.run(handler._notify_subscriber("ricf", [{"x": 1}])) is False


def test_dashboard_draws_controls_in_the_order_they_were_sent(monkeypatch):
    """켤 때(15f 200 → 14_e 200) 화면도 NCOF→NEF→RICF 를 다 그린 뒤 NCOF→PCF — 연출은 따로 돌되 순서는 지킨다."""
    drawn: list = []

    async def rec(**kwargs):
        drawn.append(f"{kwargs['from_node']}->{kwargs['to_node']}")

    monkeypatch.setattr(subscription_handler, "broadcast_web_message", rec)
    ricf = _handler_for_control(_ControlResponse(200, '{"result":"ok"}'))
    pcf = _handler_for_control(_ControlResponse(200, '{"result":"ok"}'))

    async def run():
        assert await ricf._notify_subscriber("ricf", [{"x": 1}]) is True
        assert await pcf._notify_subscriber("pcf", [{"x": 2}]) is True  # 0.5초 연출을 기다리지 않고 바로 보낸다
        await asyncio.gather(*list(subscription_handler._dashboard_tasks))

    asyncio.run(run())
    assert drawn == ["ncof->nef", "nef->ricf", "ncof->pcf"]


def test_state_save_failure_does_not_block_control(caplog):
    handler = _handler_for_control(_ControlResponse(200, '{"result":"ok"}'))

    async def broken_save():
        raise OSError("No space left on device")

    handler._on_state_change = broken_save

    async def run():
        ok = await handler._notify_subscriber("pcf", [{"x": 1}])
        await asyncio.gather(*list(subscription_handler._dashboard_tasks), return_exceptions=True)
        return ok

    with caplog.at_level("ERROR"):
        assert asyncio.run(run()) is True
    assert handler._client.posted  # 그래도 보냈다
    assert "제어 전송 전 상태 저장 실패 — 제어는 그대로 보낸다" in caplog.text


def test_control_timeout_log_names_the_error_and_target(caplog):
    handler = _handler_for_control(subscription_handler.httpx.ReadTimeout(""))
    with caplog.at_level("ERROR"):
        assert asyncio.run(handler._notify_subscriber("ricf", [{"x": 1}])) is False
    assert "제어명령 전송 중 오류 발생: ReadTimeout" in caplog.text
    assert "(http://dodo1/)" in caplog.text
