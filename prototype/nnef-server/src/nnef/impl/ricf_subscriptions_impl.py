import logging

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from nnef.apis.subscriptions_collection_api_base import BaseSubscriptionsCollectionApi
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc

from . import simulation

logger = logging.getLogger(__name__)


def get_template_file_by_event_type(event: str) -> str | None:

    # 1. 이벤트 타입별 파일 매핑 정의
    event_mapping = {
        "_POWER_ENERGY_CONSUMPTION": "13p_d_NncofEventsSubscriptionNotification_from RICF_to_NCOF_v1.0.json",
        "_RF_SIGNAL": "13p_d_NncofEventsSubscriptionNotification_from RICF_to_NCOF_v1.0.json",
        "PERF_DATA": "10p_a_NefEventExposureNotif_from_RICF_to_NCOF_v1.0.json",
    }

    return event_mapping.get(event)


class RICFImpl(BaseSubscriptionsCollectionApi):
    async def create_individual_subcription(
        self, nef_event_exposure_subsc: NefEventExposureSubsc
    ) -> JSONResponse:

        event_sub = nef_event_exposure_subsc.events_subs[0]
        if event_sub is None:
            raise HTTPException(status_code=400, detail=f"NefEventSubs is None")

        event = event_sub.event
        template_file = get_template_file_by_event_type(event)
        logger.info(f"Template file: {template_file}")

        if template_file is None:
            raise HTTPException(
                status_code=400, detail=f"Unknown event: {event_sub.event}"
            )

        return await simulation.handle_subcription_request(
            template_file, nef_event_exposure_subsc
        )
