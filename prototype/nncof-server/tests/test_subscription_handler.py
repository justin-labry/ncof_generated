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
