# coding: utf-8

from typing import Dict, List, Optional
from fastapi import HTTPException
from nncof.apis.individual_ncof_event_subscription_transfer_document_api_base import (
    BaseIndividualNCOFEventSubscriptionTransferDocumentApi,
)
from nncof.models.analytics_subscriptions_transfer import AnalyticsSubscriptionsTransfer


class IndividualNCOFEventSubscriptionTransferDocumentApiImpl(
    BaseIndividualNCOFEventSubscriptionTransferDocumentApi
):
    """
    Implementation of Individual NCOF Event Subscription Transfer Document API
    """

    # In-memory storage for transfers (in a real app, this would be a database)
    _transfers: Dict[str, AnalyticsSubscriptionsTransfer] = {}

    async def update_ncof_event_subscription_transfer(
        self,
        transferId: str,
        analytics_subscriptions_transfer: AnalyticsSubscriptionsTransfer,
    ) -> None:
        """
        Update an existing NCOF event subscription transfer
        """
        # Update the transfer
        self._transfers[transferId] = analytics_subscriptions_transfer

    async def delete_ncof_event_subscription_transfer(
        self,
        transferId: str,
    ) -> None:
        """
        Delete an existing NCOF event subscription transfer
        """
        # Check if transfer exists
        if transferId not in self._transfers:
            raise HTTPException(status_code=404, detail="Transfer not found")

        # Delete the transfer
        del self._transfers[transferId]
