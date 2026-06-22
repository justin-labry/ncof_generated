from datetime import datetime
from typing import Dict, List

from nncof.models.nncof_events_subscription_notification import (
    NncofEventsSubscriptionNotification,
)
from pydantic import TypeAdapter

from .decide_wlan_gnb2_rule import (
    extract_wlan_dl_mbps,
    decide_gnb2_state,
    build_15f_cell_power,
    apply_qos_policy,
)


class Gnb2RuleEngine:
    def __init__(self, th_mbps=500.0, min_dwell_sec=0):
        self.th_mbps = th_mbps
        self.min_dwell_sec = min_dwell_sec  # 0 = 가드 비활성 (기본)
        self.last_emitted_state = None  # emit-on-change 추적용
        self.last_change_at = None  # minimum-dwell guard용

    def _decide(self, metric: float) -> str:
        """
        WLAN metric → gNB2 상태 판정. RL 엔진은 이 메서드만 오버라이드한다.
        (emit-on-change / dwell guard / 15f·14_e 생성은 공통 로직 공유)
        """
        return decide_gnb2_state(metric, self.th_mbps)

    def generate_notification(
        self,
        notif_12p_c: dict,
        qos_template: list[dict],
        decision_iso: str,
        sub_id: str,
        corr_id: str | None,
    ) -> Dict[str, List[dict]] | None:
        metric = extract_wlan_dl_mbps(notif_12p_c)
        new_state = self._decide(metric)

        if new_state == self.last_emitted_state:
            return None  # no change → 통지 안 보냄

        # 선택적 minimum-dwell guard (flap 방지)
        if self.min_dwell_sec and self.last_change_at:
            elapsed = (
                datetime.fromisoformat(decision_iso) - self.last_change_at
            ).total_seconds()
            if elapsed < self.min_dwell_sec:
                return None  # 직전 변경 후 dwell 시간 안 됨 → 보류

        self.last_emitted_state = new_state
        self.last_change_at = datetime.fromisoformat(decision_iso)
        # return {
        #     "cell_power_15f": NncofEventsSubscriptionNotification.from_dict(
        #         build_15f_cell_power(new_state, decision_iso, sub_id, corr_id)[0]
        #     ),
        #     "qos_policy_14e": NncofEventsSubscriptionNotification.from_dict(
        #         apply_qos_policy(qos_template, new_state)[0]
        #     ),
        # }

        return {
            "cell_power_15f": build_15f_cell_power(
                new_state, decision_iso, sub_id, corr_id
            ),
            "qos_policy_14e": apply_qos_policy(qos_template, new_state),
        }


def _convert_(qos_template: list[dict]) -> NncofEventsSubscriptionNotification:
    try:
        adapter = TypeAdapter(list[NncofEventsSubscriptionNotification])
        validated_list = adapter.validate_python(qos_template)

        # 파싱 성공 후 첫 번째 객체 출력
        result = validated_list[0]
        return result

    except Exception as e:
        # 💡 만약 구조가 단일 객체라면 방법 2로 우회합니다.
        # 방법 2: 리스트의 첫 번째 요소를 꺼내 모델 검증에 통째로 전달
        result = NncofEventsSubscriptionNotification.model_validate(qos_template[0])
        return result


# def _convert(
#     qos_template: list[dict],
# ) -> List[NncofEventsSubscriptionNotification]:
#     return qos_template
