import logging

import json

from pathlib import Path


from pydantic import TypeAdapter
from rich.pretty import pprint as rprint


from nncof.models.nncof_events_subscription_notification import (
    NncofEventsSubscriptionNotification,
)

logger = logging.getLogger(__name__)


# JSON 문서 파싱 테스트
#
qos_template_file = (
    # "15f_NncofEventsSubscriptionNotification_from NCOF_to_RICF_v1.0.json"
    "14_e_NncofEventsSubscriptionNotification_from NCOF_to_PCF_v1.0.json"
)
qos_template_file_path = Path(__file__).parent / qos_template_file

with open(qos_template_file_path, "r", encoding="utf-8") as f:
    qos_template = json.load(f)

# rprint(NncofEventsSubscriptionNotification.from_dict(qos_template[0]))
# rprint(qos_template)

try:
    adapter = TypeAdapter(list[NncofEventsSubscriptionNotification])
    validated_list = adapter.validate_python(qos_template)

    # 파싱 성공 후 첫 번째 객체 출력
    rprint(validated_list)
except Exception as e:
    # 💡 만약 구조가 단일 객체라면 방법 2로 우회합니다.
    # 방법 2: 리스트의 첫 번째 요소를 꺼내 모델 검증에 통째로 전달
    rprint(NncofEventsSubscriptionNotification.model_validate(qos_template[0]))
