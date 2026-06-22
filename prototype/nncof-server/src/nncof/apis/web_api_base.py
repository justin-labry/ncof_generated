# coding: utf-8
# web_api 라우터의 Base 클래스 — Impl 패턴을 위한 인터페이스 정의

from typing import ClassVar, Dict, List, Tuple, Any


class BaseWebApi:
    """웹 대시보드 API의 구현부를 분리하기 위한 Base 클래스"""
    subclasses: ClassVar[Tuple[type, ...]] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseWebApi.subclasses = BaseWebApi.subclasses + (cls,)

    async def get_status(self) -> Dict[str, Any]:
        ...

    async def get_subscription_relations(self) -> List[Dict[str, Any]]:
        ...

    async def get_subscriptions(self) -> List[Dict[str, Any]]:
        ...

    async def get_notifications(self) -> Dict[str, Any]:
        ...

    async def get_notification_by_id(self, sub_id: str) -> Dict[str, Any]:
        ...

    async def get_control_notifications(self) -> Dict[str, Any]:
        ...

    async def get_handlers(self) -> List[Dict[str, Any]]:
        ...
