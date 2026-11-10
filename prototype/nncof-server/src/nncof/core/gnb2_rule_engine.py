import itertools
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
        # level 모드 — 경계로 단계를 정하고 단계별 gNB2 · gNB1 몫으로 쌍마다 split_total 을 나눈다(decision_config 참조)
        self.level_bounds_mbps: tuple[float, ...] = (172.0, 305.0, 338.0)
        self.level_gnb2_pct: tuple[int, ...] = (0, 50, 70, 90)
        self.level_gnb1_pct: tuple[int, ...] = (30, 50, 70, 90)
        self.split_total_mbps = 1000
        self.down_confirm_samples = 1  # level 모드 내림 확인 샘플 수(1 = 곧바로)
        # level 모드에서 이번 단계를 정한 까닭(로그용) — 선제 · 사후 · 내림 대기
        self.last_level_note: str | None = None
        self.last_emitted_state = None  # emit-on-change 추적용
        self.last_change_at = None  # minimum-dwell guard용
        # level 모드에서 지금 상태와 함께 내보낼 단계 · (NR gNB2, WLAN) · (NR gNB1, WLAN) gbr/mbr. 그 밖의 모드는 None
        self.last_emitted_level: int | None = None
        self.last_emitted_split: tuple[int, int] | None = None
        self.last_emitted_gnb1_split: tuple[int, int] | None = None

    def apply_config(self, config) -> None:
        """판정 설정(decision_config.Gnb2DecisionConfig)을 반영한다 — 연동 중 임계 조정용."""
        self.th_mbps = config.th_mbps
        self.hyst_mbps = config.hyst_mbps
        self.min_dwell_sec = config.min_dwell_sec
        self.mode = config.mode
        self.trend_deadband_mbps = config.trend_deadband_mbps
        self.level_bounds_mbps = config.level_bounds_mbps
        self.level_gnb2_pct = config.level_gnb2_pct
        self.level_gnb1_pct = config.level_gnb1_pct
        self.split_total_mbps = config.split_total_mbps
        self.down_confirm_samples = config.down_confirm_samples

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

    def update_state(
        self,
        metric: float,
        decision_iso: str,
        prev_metric: float | None = None,
        *,
        recent_mbps: list[float] | None = None,
        forecast_mbps: float | None = None,
    ) -> str:
        """
        metric 으로 판정해 확정된 현재 gNB2 상태를 반환한다.
        판정이 바뀌어도 minimum-dwell guard 에 걸리면 직전 상태를 유지한다.
        (15f·14_e 생성 없이 상태만 필요한 DataAnalyzer 의 fan-out 경로가 쓴다)
        prev_metric 은 trend 모드에서만 쓰는, 같은 12p_c 스트림을 지난 판정 때 본 값이다.
        level 모드면 확정된 상태에 맞는 단계·split 도 last_emitted_level/last_emitted_split 에 남긴다.
        recent_mbps(최근 12p_c 샘플, 오래된 것 먼저) · forecast_mbps(앞으로 lead 초 안의 예측 최대)는 룰 엔진
        level 모드에서만 쓴다 — _update_level_mode 참조. _decide 를 바꾼 엔진(RL)은 예전 경로 그대로다.
        """
        if self.mode == "level" and type(self)._decide is Gnb2RuleEngine._decide:
            return self._update_level_mode(metric, decision_iso, recent_mbps, forecast_mbps)
        self.last_level_note = None
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
            self.last_emitted_gnb1_split = None
            return
        level = level_index(metric, self.level_bounds_mbps)
        if state == "DEEP_SLEEP":
            level = 0
        elif level == 0:
            level = 1  # dwell(또는 RL 판정)이 ACTIVE 를 붙잡고 있을 때 — ACTIVE 중 가장 낮은 단계
        self._set_level(level)

    def _update_level_mode(
        self,
        metric: float,
        decision_iso: str,
        recent_mbps: list[float] | None,
        forecast_mbps: float | None,
    ) -> str:
        """level 모드(룰 엔진) — 오를 때는 선제, 내릴 때는 사후.

        - 오름: 지금 값의 단계나 예측 단계(forecast_mbps — 앞으로 lead 초 안의 최대) 중 높은 쪽이 지금 단계보다 높으면 곧바로.
        - 내림: 지금 값의 단계가 낮아져도 최근 샘플 down_confirm_samples 개(지금 값 포함)가 모두 같은 단계일 때만 그 단계로
          (예측이 그보다 높으면 예측 단계까지만). 경계를 걸친 평균 샘플 하나로 중간 단계(예: 5:5 → 3:7 → DEEP_SLEEP)를
          거치지 않게 한다. recent_mbps 가 None 이면 확인 없이 곧바로(예전 그대로).
        - 단계 0 이면 DEEP_SLEEP, 그 위는 ACTIVE. minimum-dwell 은 상태(셀) 변경에만 건다(예전과 같다).
        """
        bounds = self.level_bounds_mbps
        now_level = level_index(metric, bounds)
        pred_level = level_index(forecast_mbps, bounds) if forecast_mbps is not None else 0
        up = max(now_level, pred_level)
        held = self.last_emitted_level
        if held is None or up > held:
            target = up
            if held is None:
                note = "첫 판정"
            elif pred_level > now_level:
                note = f"선제 — 예측 {forecast_mbps:.0f} Mbps(단계 {pred_level})"
            else:
                note = "사후 — 지금 값"
        elif now_level < held and pred_level >= held:
            target = held
            note = f"선제 유지 — 예측 {forecast_mbps:.0f} Mbps(단계 {pred_level})"
        elif now_level < held:
            n = max(1, self.down_confirm_samples)
            # recent_mbps 의 마지막은 보통 지금 값과 같은 샘플이다 — 그 앞까지 n 개(지금 값 포함)가 같은 단계여야 한다
            window = [] if recent_mbps is None else [*list(recent_mbps)[-n:], metric]
            if recent_mbps is None or n == 1 or (
                len(window) > n and {level_index(v, bounds) for v in window} == {now_level}
            ):
                target = max(now_level, pred_level)
                note = "사후 — 내림" + (f"(샘플 {n}개 확인)" if n > 1 else "")
            else:
                target = held
                same = itertools.takewhile(lambda v: level_index(v, bounds) == now_level, reversed(window[:-1]))
                note = f"내림 대기 — 단계 {now_level} 샘플 {min(sum(1 for _ in same), n)}/{n}"
        else:
            target = held
            note = None
        state = "DEEP_SLEEP" if target == 0 else "ACTIVE"
        if state != self.last_emitted_state:
            if self.last_emitted_state is not None and self._dwell_holds(decision_iso):
                state = self.last_emitted_state
                target = 0 if state == "DEEP_SLEEP" else max(target, 1)
                note = f"최소 유지 시간 — {state} 유지"
            else:
                self.last_emitted_state = state
                self.last_change_at = datetime.fromisoformat(decision_iso)
        self.last_level_note = note
        self._set_level(target)
        return self.last_emitted_state

    def _set_level(self, level: int) -> None:
        self.last_emitted_level = level
        self.last_emitted_split = split_for_pct(self.level_gnb2_pct[level], self.split_total_mbps)
        # gNB1 은 잠들지 않는다 — 노트북1 쌍은 같은 단계의 gNB1 몫(단계 0 에도 0 이 아닐 수 있다). 몫이 비면 끔(gNB1 set 그대로)
        self.last_emitted_gnb1_split = (
            split_for_pct(self.level_gnb1_pct[level], self.split_total_mbps) if self.level_gnb1_pct else None
        )

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
                qos_template, new_state, decision_iso, sub_id, corr_id,
                self.last_emitted_split, self.last_emitted_gnb1_split,
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
