# coding: utf-8

from typing import Dict, List, Optional
from fastapi import HTTPException
from nncof.apis.individual_ncof_events_subscription_document_api_base import BaseIndividualNCOFEventsSubscriptionDocumentApi
from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nncof.models.problem_details import ProblemDetails
from nncof.core.subscription_manager import SubscriptionManager

class IndividualNCOFEventsSubscriptionDocumentApiImpl(BaseIndividualNCOFEventsSubscriptionDocumentApi):
    """
    Implementation of Individual NCOF Events Subscription Document API
    """

    async def update_ncof_events_subscription(
        self,
        subscriptionId: str,
        nncof_events_subscription: NncofEventsSubscription,
    ) -> NncofEventsSubscription:
        """
        기존 NCOF 이벤트 구독 정보를 업데이트한다.
        """
        manager = SubscriptionManager()
        success = await manager.update_subscription(subscriptionId, nncof_events_subscription)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Subscription {subscriptionId} not found")
            
        return nncof_events_subscription

    async def delete_ncof_events_subscription(
        self,
        subscriptionId: str,
    ) -> None:
        """
        기존 NCOF 이벤트 구독을 삭제하고 관련 리소스를 정리한다.
        """
        manager = SubscriptionManager()
        
        # SubscriptionManager를 통해 구독 삭제 및 관련 외부 NF 구독 해지 수행
        success = await manager.delete_subscription(subscriptionId)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Subscription {subscriptionId} not found")