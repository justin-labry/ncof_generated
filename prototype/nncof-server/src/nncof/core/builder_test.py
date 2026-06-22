# subscription_pcf_to_ncof.json 파일을 읽어 NncofEventsSubscription.from_dict()로 객체 생성하는 테스트
import json
import os
from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from rich.pretty import pprint as rprint
from nncof.core.subscription_request_builder import (
    build_subscription_requests,
    ExternalSubscriptionRequest,
)

_json_path = os.path.join(os.path.dirname(__file__), "subscription_pcf_to_ncof.json")

with open(_json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

subscription = NncofEventsSubscription.from_dict(data)

# print(f"객체 생성 완료: eventSubscriptions={len(subscription.event_subscriptions)}개")
# print(f"notificationURI={subscription.notification_uri}")
# print(f"notifCorrId={subscription.notif_corr_id}")
# print(f"supportedFeatures={subscription.supported_features}")

results = build_subscription_requests("subscription_id_001", subscription)


# iterate results

for item in results:
    # if isinstance(x.subscription, NefEventExposureSubsc):
    # rprint("ok")
    if isinstance(item["subscription"], NefEventExposureSubsc):
        r = NefEventExposureSubsc.from_dict(
            item["subscription"] if item["subscription"] else {}
        )
        rprint(r.events_rep_info)
