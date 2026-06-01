# coding: utf-8

from typing import Dict
import uuid

from fastapi import HTTPException

from nncof.apis.ncof_events_subscriptions_collection_api_base import (
    BaseNCOFEventsSubscriptionsCollectionApi,
)

from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nncof.core.subscription_manager import SubscriptionManager
from fastapi.responses import JSONResponse

from fastapi.encoders import jsonable_encoder
from nncof.core.websocket_manager import manager, broadcast_web_message


class NCOFEventsSubscriptionsCollectionApiImpl(
    BaseNCOFEventsSubscriptionsCollectionApi
):
    """
    Implementation of NCOF Events Subscriptions Collection API
    """

    async def create_ncof_events_subscription(
        self,
        nncof_events_subscription: NncofEventsSubscription,
    ):
        """
        Create a new NCOF events subscription
        """

        # SubscriptionManager 싱글톤 인스턴스 획득
        manager = SubscriptionManager()

        try:
            # 구독 생성 및 외부 NF 구독 절차 시작
            subscription_id = await manager.create_subscription(
                nncof_events_subscription
            )

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to create subscription: {str(e)}"
            )

        # 생성된 구독 ID를 헤더에 포함하여 응답 반환
        return JSONResponse(
            content=jsonable_encoder(nncof_events_subscription),
            headers={"Subscription-ID": subscription_id},
            status_code=201,
        )
