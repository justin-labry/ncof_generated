import logging
from rich.pretty import pretty_repr

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

logger = logging.getLogger(__name__)
class Gnb2RuleEngine:
    def __init__(self, th_mbps=500.0, min_dwell_sec=0, hyst_mbps=0.0):
        self.th_mbps = th_mbps
        self.hyst_mbps = hyst_mbps  # 0 = 히스테리시스 비활성 (기본)
        self.min_dwell_sec = min_dwell_sec  # 0 = 가드 비활성 (기본)
        self.last_emitted_state = None  # emit-on-change 추적용
        self.last_change_at = None  # minimum-dwell guard용

    def apply_config(self, config) -> None:
        """판정 설정(decision_config.Gnb2DecisionConfig)을 반영한다 — 연동 중 임계 조정용."""
        self.th_mbps = config.th_mbps
        self.hyst_mbps = config.hyst_mbps
        self.min_dwell_sec = config.min_dwell_sec

    def _decide(self, metric: float) -> str:
        """
        WLAN metric → gNB2 상태 판정. RL 엔진은 이 메서드만 오버라이드한다.
        (emit-on-change / dwell guard / 15f·14_e 생성은 공통 로직 공유)

        히스테리시스: ACTIVE 에서는 metric < th - hyst 일 때만 DEEP_SLEEP 으로 내려간다.
        12p_c 는 매 주기 수 Mbps 씩 흔들리므로(9/30 실측 282~292) 임계를 그 대역에 두면 매 틱 뒤집힌다.
        """
        if self.hyst_mbps and self.last_emitted_state == "ACTIVE":
            return decide_gnb2_state(metric, self.th_mbps - self.hyst_mbps)
        return decide_gnb2_state(metric, self.th_mbps)

    def update_state(self, metric: float, decision_iso: str) -> str:
        """
        metric 으로 판정해 확정된 현재 gNB2 상태를 반환한다.
        판정이 바뀌어도 minimum-dwell guard 에 걸리면 직전 상태를 유지한다.
        (15f·14_e 생성 없이 상태만 필요한 DataAnalyzer 의 fan-out 경로가 쓴다)
        """
        new_state = self._decide(metric)

        if new_state == self.last_emitted_state:
            return new_state

        # 선택적 minimum-dwell guard (flap 방지)
        if self.min_dwell_sec and self.last_change_at:
            elapsed = (
                datetime.fromisoformat(decision_iso) - self.last_change_at
            ).total_seconds()
            if elapsed < self.min_dwell_sec:
                return self.last_emitted_state  # 직전 변경 후 dwell 시간 안 됨 → 보류

        self.last_emitted_state = new_state
        self.last_change_at = datetime.fromisoformat(decision_iso)
        return new_state

    def generate_notification(
        self,
        notif_12p_c: dict,
        qos_template: list[dict],
        decision_iso: str,
        sub_id: str,
        corr_id: str | None,
    ) -> Dict[str, List[dict]] | None:
        metric = extract_wlan_dl_mbps(notif_12p_c)
        logger.info(f"분석 메트릭 WLAN_DL_MBPS:{metric}")

        logger.info("AI 분석 시작")
        prev_state = self.last_emitted_state
        new_state = self.update_state(metric, decision_iso)

        if new_state == prev_state:
            return None  # no change(또는 dwell 보류) → 통지 안 보냄

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
            "qos_policy_14e": apply_qos_policy(
                qos_template, new_state, decision_iso, sub_id, corr_id
            ),
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
