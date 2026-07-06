# coding: utf-8

from typing import Any, Dict, List

from nncof.apis.web_api_base import BaseWebApi
from nncof.core.subscription_manager import SubscriptionManager

from nncof.core.utils import system_info


class WebApiImpl(BaseWebApi):
    """웹 대시보드 API 구현"""

    async def get_status(self) -> Dict[str, Any]:
        return system_info()

    async def get_subscription_relations(self) -> List[Dict[str, Any]]:
        manager = SubscriptionManager()
        return manager.get_active_relations()

    async def get_subscriptions(self) -> List[Dict[str, Any]]:
        manager = SubscriptionManager()
        return manager.get_subscriptions()

    async def get_notifications(self) -> Dict[str, Any]:
        manager = SubscriptionManager()
        return manager.get_notifications()

    async def get_notification_by_id(self, sub_id: str) -> Dict[str, Any]:
        manager = SubscriptionManager()
        return manager.get_notification_by_id(sub_id)

    async def get_control_notifications(self) -> Dict[str, Any]:
        manager = SubscriptionManager()
        return manager.get_control_notifications()

    async def get_handlers(self) -> List[Dict[str, Any]]:
        manager = SubscriptionManager()
        return manager.get_handlers()
