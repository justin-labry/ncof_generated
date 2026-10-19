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
    level_index,
    split_for_pct,
)

logger = logging.getLogger(__name__)
class Gnb2RuleEngine:
    def __init__(self, th_mbps=500.0, min_dwell_sec=0, hyst_mbps=0.0):
        self.th_mbps = th_mbps
        self.hyst_mbps = hyst_mbps  # 0 = 히스테리시스 비활성 (기본)
        self.min_dwell_sec = min_dwell_sec  # 0 = 가드 비활성 (기본)
        self.mode = "threshold"  # "trend" = 임계 이상에서 같은 12p_c 스트림의 지난 판정 때 값 대비 추세로 판정
        self.trend_deadband_mbps = 0.0
        # level 모드 — 경계로 단계를 정하고 단계별 gNB2 몫으로 split_total 을 나눈다(decision_config 참조)
        self.level_bounds_mbps: tuple[float, ...] = (172.0, 305.0, 338.0)
        self.level_gnb2_pct: tuple[int, ...] = (0, 50, 70, 90)
        self.split_total_mbps = 1000
        self.last_emitted_state = None  # emit-on-change 추적용
        self.last_change_at = None  # minimum-dwell guard용
        # level 모드에서 지금 상태와 함께 내보낼 단계 · (NR gNB2, WLAN) gbr/mbr. 그 밖의 모드는 None
        self.last_emitted_level: int | None = None
        self.last_emitted_split: tuple[int, int] | None = None

    def apply_config(self, config) -> None:
        """판정 설정(decision_config.Gnb2DecisionConfig)을 반영한다 — 연동 중 임계 조정용."""
        self.th_mbps = config.th_mbps
        self.hyst_mbps = config.hyst_mbps
        self.min_dwell_sec = config.min_dwell_sec
        self.mode = config.mode
        self.trend_deadband_mbps = config.trend_deadband_mbps
        self.level_bounds_mbps = config.level_bounds_mbps
        self.level_gnb2_pct = config.level_gnb2_pct
        self.split_total_mbps = config.split_total_mbps

    def _decide(self, metric: float, prev_metric: float | None = None) -> str:
        """
        WLAN metric → gNB2 상태 판정. RL 엔진은 이 메서드만 오버라이드한다.
        (emit-on-change / dwell guard / 15f·14_e 생성은 공통 로직 공유)

        히스테리시스: ACTIVE 에서는 metric < th - hyst 일 때만 DEEP_SLEEP 으로 내려간다.
        12p_c 는 매 주기 수 Mbps 씩 흔들리므로(9/30 실측 282~292) 임계를 그 대역에 두면 매 틱 뒤집힌다.

        trend 모드: 임계 미만은 위와 같이 DEEP_SLEEP. 임계 이상이면 지난 판정 때 본 값(prev_metric)과 비교해
        오르면 ACTIVE, 내리면 DEEP_SLEEP, 차이가 데드밴드 이하면 현재 상태 유지.
        다음은 임계 규칙 그대로(임계 이상 = ACTIVE): 첫 판정, 지난 판정 값이 없을 때(끊긴 뒤), 지난 판정 값이 임계 미만이었을 때(아래에서 넘어옴).

        level 모드: 첫 경계 미만(단계 0)이면 DEEP_SLEEP, 그 위는 ACTIVE. TH·히스테리시스·trend 는 쓰지 않는다.
        """
        if self.mode == "level":
            return decide_gnb2_state(metric, self.level_bounds_mbps[0])
        if self.hyst_mbps and self.last_emitted_state == "ACTIVE":
            state = decide_gnb2_state(metric, self.th_mbps - self.hyst_mbps)
        else:
            state = decide_gnb2_state(metric, self.th_mbps)
        if (
            self.mode != "trend"
            or state != "ACTIVE"
            or self.last_emitted_state is None
            or prev_metric is None
            or prev_metric < self.th_mbps
        ):
            return state

        delta = metric - prev_metric
        if delta > self.trend_deadband_mbps:
            return "ACTIVE"
        if delta < -self.trend_deadband_mbps:
            return "DEEP_SLEEP"
        return self.last_emitted_state

    def update_state(self, metric: float, decision_iso: str, prev_metric: float | None = None) -> str:
        """
        metric 으로 판정해 확정된 현재 gNB2 상태를 반환한다.
        판정이 바뀌어도 minimum-dwell guard 에 걸리면 직전 상태를 유지한다.
        (15f·14_e 생성 없이 상태만 필요한 DataAnalyzer 의 fan-out 경로가 쓴다)
        prev_metric 은 trend 모드에서만 쓰는, 같은 12p_c 스트림을 지난 판정 때 본 값이다.
        level 모드면 확정된 상태에 맞는 단계·split 도 last_emitted_level/last_emitted_split 에 남긴다.
        """
        new_state = self._decide(metric, prev_metric)

        if new_state != self.last_emitted_state and not self._dwell_holds(decision_iso):
            self.last_emitted_state = new_state
            self.last_change_at = datetime.fromisoformat(decision_iso)
        self._update_level(metric)
        return self.last_emitted_state

    def _dwell_holds(self, decision_iso: str) -> bool:
        """선택적 minimum-dwell guard (flap 방지) — 직전 변경 후 dwell 시간이 안 됐으면 True(변경 보류)."""
        if not (self.min_dwell_sec and self.last_change_at):
            return False
        elapsed = (datetime.fromisoformat(decision_iso) - self.last_change_at).total_seconds()
        return elapsed < self.min_dwell_sec

    def _update_level(self, metric: float) -> None:
        """level 모드: 확정된 상태에 맞춰 단계를 정한다 — DEEP_SLEEP 이면 단계 0(gNB2 0) 불변식을 지킨다."""
        state = self.last_emitted_state
        if self.mode != "level" or state is None:
            self.last_emitted_level = None
            self.last_emitted_split = None
            return
        level = level_index(metric, self.level_bounds_mbps)
        if state == "DEEP_SLEEP":
            level = 0
        elif level == 0:
            level = 1  # dwell(또는 RL 판정)이 ACTIVE 를 붙잡고 있을 때 — ACTIVE 중 가장 낮은 단계
        self.last_emitted_level = level
        self.last_emitted_split = split_for_pct(self.level_gnb2_pct[level], self.split_total_mbps)

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
                qos_template, new_state, decision_iso, sub_id, corr_id, self.last_emitted_split
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
