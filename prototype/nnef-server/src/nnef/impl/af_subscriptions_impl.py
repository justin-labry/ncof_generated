import logging

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from nnef.apis.subscriptions_collection_api_base import BaseSubscriptionsCollectionApi
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc

from . import simulation

logger = logging.getLogger(__name__)


def get_sample_file(nef_event_exposure_subsc: NefEventExposureSubsc):
    event_sub = nef_event_exposure_subsc.events_subs[0]
    if event_sub is None:
        raise HTTPException(status_code=400, detail=f"NefEventSubs is None")

    sample_file = None
    event = event_sub.event

    app_ids = getattr(event_sub.event_filter, "app_ids", None)

    if event == "PERF_DATA" and app_ids and len(app_ids) == 2:
        sample_file = "9p_NefEventExposureNotif_from_AF_to_NCOF_v1.0.json"
    elif event_sub.event == "PERF_DATA" and app_ids and len(app_ids) == 4:
        sample_file = "9_NefEventExposureNotif_from_AF_to_NCOF_v1.0.json"
    elif event == "DISPERSION":
        sample_file = "11p_b_NefEventExposureNotif_from_AF_to_NCOF_v1.0.json"
    return sample_file


class AFImpl(BaseSubscriptionsCollectionApi):
    async def create_individual_subcription(
        self, nef_event_exposure_subsc: NefEventExposureSubsc
    ) -> JSONResponse:

        event_sub = nef_event_exposure_subsc.events_subs[0]
        if event_sub is None:
            raise HTTPException(status_code=400, detail=f"NefEventSubs is None")

        sample_file = get_sample_file(nef_event_exposure_subsc)

        if sample_file is None:
            raise HTTPException(
                status_code=400, detail=f"Unknown event: {event_sub.event}"
            )

        print(f"AF - {sample_file}")

        return await simulation.handle_subcription_request(
            sample_file, nef_event_exposure_subsc
        )

        # return nef_event_exposure_subsc
