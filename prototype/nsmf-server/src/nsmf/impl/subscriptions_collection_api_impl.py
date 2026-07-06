from typing import Dict
import uuid
import asyncio

from datetime import datetime, timezone
from rich.pretty import pprint

from nupf.models.notification_data import NotificationData

from nsmf.apis.subscriptions_collection_api_base import BaseSubscriptionsCollectionApi
from nsmf.models.nsmf_event_exposure import NsmfEventExposure
from nsmf.impl.simulation import simulate_notification_data
from . import utils
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

import logging

logger = logging.getLogger(__name__)

_subscriptions: Dict[str, dict] = {}


class NCOFEventsSubscriptionsCollectionApiImpl(BaseSubscriptionsCollectionApi):
    async def create_individual_subcription(
        self,
        nsmf_event_exposure: NsmfEventExposure,
    ):

        upf_events = nsmf_event_exposure.event_subs[0].upf_events
        sample_file = ""

        # 목업 기능 구현을 위해서 특정 필드를 사용해서 데이터 생성
        if upf_events:
            # just for test
            if len(upf_events) == 5:
                sample_file = "8_NotificationData_from_UPF_to_NCOF_v1.0.json"
            elif len(upf_events) == 3:
                sample_file = "8p_NotificationData_from_UPF_to_NCOF_v1.0.json"
            else:
                sample_file = "12_c_NotificationData_from_UPF_to_NCOF_v1.0.json"
        logger.info(f"Read template: {sample_file}")

        payload = utils.load_json(sample_file)

        notification_data = NotificationData.from_dict(payload)

        sub_id = str(uuid.uuid4())
        nsmf_event_exposure.sub_id = sub_id

        notification_data.correlation_id = nsmf_event_exposure.notif_id

        _subscriptions[sub_id] = {
            "event_subscription": nsmf_event_exposure,
            "event_notification": notification_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        rep_period = nsmf_event_exposure.rep_period or 10

        logger.info(f"rep_period: {rep_period}")
        asyncio.create_task(
            _periodic_notification_sender(sub_id, interval_seconds=rep_period)
        )

        # return nsmf_event_exposure

        return JSONResponse(
            content=jsonable_encoder(nsmf_event_exposure),
            headers={"Subscription-ID": sub_id},
            status_code=201,
        )


async def _periodic_notification_sender(sub_id: str, interval_seconds: int):
    while True:

        subscription_info = _subscriptions.get(sub_id)
        if subscription_info is None:
            break

        event_subscription: NsmfEventExposure = subscription_info["event_subscription"]
        event_notification: NotificationData = subscription_info["event_notification"]

        expiry = event_subscription.expiry
        if expiry:
            if datetime.now(timezone.utc) >= expiry:
                logger.warning(
                    f"[{sub_id}] Expiry time reached. Stopping notification sender."
                )
                del _subscriptions[sub_id]
                break

        notif_uri = event_subscription.notif_uri
        await asyncio.sleep(interval_seconds)
        notification_data = simulate_notification_data(sub_id, event_notification)
        pprint(notification_data.notification_items[0])

        # print(f"[{sub_id}] 💡---[Notification]---> [NCOF] [Begin]")
        # for item in notification_data.notification_items:
        #     if item is None:
        #         continue
        #     for item2 in (
        #         item.user_data_usage_measurements
        #         if item.user_data_usage_measurements
        #         else []
        #     ):
        #         pprint(item2)
        # print(f"[{sub_id}] 💡---[Notification]---> [NCOF] [End]")
        # pprint(notification_data.model_dump(mode="json"))
        await utils.notify(sub_id, notif_uri, notification_data.model_dump(mode="json"))
