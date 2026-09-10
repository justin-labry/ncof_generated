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
