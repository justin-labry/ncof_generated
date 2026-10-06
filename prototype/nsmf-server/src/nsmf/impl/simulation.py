import os
import random
import re
import asyncio
from typing import Optional

from datetime import datetime, timezone

import logging

logger = logging.getLogger(__name__)

from nupf.models.notification_data import NotificationData

_dl_throughput_high = True

# DL throughput High/Low 토글 주기(초). main.py 의 start_dl_throughput_toggle 과
# 재현 모드의 주기 수 기반 토글(dl_throughput_high_at)이 같은 값을 쓴다.
DL_TOGGLE_INTERVAL_SECONDS = 6


# ------------------------------------------------------------------------------
# 재현 가능한 시뮬레이션 (SIM_SEED)
# ------------------------------------------------------------------------------
# SIM_SEED 가 설정되어 있으면(prototype/ncof_setting.conf) 구독마다 독립된
# random.Random 을 쓰고, DL throughput High/Low 토글도 벽시계 대신 "구독 이후
# 몇 번째 통지인가"로 결정한다. 벽시계 토글은 서버 기동 시각과 구독 시각의
# 위상차에 따라 High/Low 가 갈리므로 시드를 고정해도 결과가 달라진다.
# 시드 키는 실행마다 바뀌는 sub_id(uuid4)·notifId(생성 시각 포함)가 아니라
# "템플릿 파일 + 같은 키의 n번째 구독" 이다.
# SIM_SEED 가 비어 있으면 기존 동작(전역 random, 벽시계 토글)을 그대로 쓴다.
_seed_counters: dict[str, int] = {}


def sim_seed() -> Optional[str]:
    return os.getenv("SIM_SEED", "").strip() or None


def make_rng(key: str):
    seed = sim_seed()
    if seed is None:
        return random
    n = _seed_counters.get(key, 0)
    _seed_counters[key] = n + 1
    # 문자열 시드는 PYTHONHASHSEED 와 무관하게 결정적이다(sha512 기반).
    rng = random.Random(f"{seed}|{key}|{n}")
    logger.info(f"[SIM_SEED={seed}] rng key: {key}#{n}")
    return rng


def dl_throughput_high_at(tick: int, interval_seconds: float) -> bool:
    """구독 후 tick 번째 통지 시점(가상 시간 tick*interval)의 High/Low.
    t=0 에서 High 로 시작해 DL_TOGGLE_INTERVAL_SECONDS 마다 뒤집히는 원래
    토글을 벽시계 대신 가상 시간으로 재현한다."""
    elapsed = tick * interval_seconds
    return int(elapsed // DL_TOGGLE_INTERVAL_SECONDS) % 2 == 0


async def start_dl_throughput_toggle(interval_seconds: int = 10):
    """
    서버 시작시 호출되어 주기적으로 _dl_throughput_high 값을 토글한다.
    """
    global _dl_throughput_high
    while True:
        await asyncio.sleep(interval_seconds)
        # logger.info(
        #     f"💢 Toggle dl_throughput: { 'High' if _dl_throughput_high else 'Low'}"
        # )
        _dl_throughput_high = not _dl_throughput_high


def _vary_int(
    value: Optional[int],
    min_delta: int,
    max_delta: int,
    max_val: Optional[int] = None,
    rng=random,
) -> Optional[int]:
    if value is None:
        return None
    new_val = value + rng.randint(min_delta, max_delta)
    if max_val is not None:
        new_val = min(new_val, max_val)
    return max(0, new_val)


def _vary_float(
    value: Optional[float], min_delta: float, max_delta: float, rng=random
) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, round(value + rng.uniform(min_delta, max_delta), 2))


def _parse_number_unit(text: str):
    """Parse '150 Mbps' -> (150.0, 'Mbps')"""
    match = re.match(r"([\d.]+)\s*(.+)", text)
    if match:
        return float(match.group(1)), match.group(2).strip()
    return None, text


def _vary_metric_str(
    value: Optional[str], factor: float = 0.1, rng=random
) -> Optional[str]:
    """Vary a metric string like '150 Mbps' by +/- factor%"""
    if value is None:
        return None
    num, unit = _parse_number_unit(value)
    if num is None:
        return value
    delta = num * rng.uniform(-factor, factor)
    new_num = max(0.0, num + delta)
    if new_num >= 10:
        return f"{new_num:.0f} {unit}"
    return f"{new_num:.1f} {unit}"


def _increment_volume_str(
    value: Optional[str], inc_range: tuple[float, float] = (0.1, 0.5), rng=random
) -> Optional[str]:
    """Increment a volume string like '3 GB' by a random amount"""
    if value is None:
        return None
    num, unit = _parse_number_unit(value)
    if num is None:
        return value
    inc = rng.uniform(*inc_range)
    new_num = num + inc
    if new_num >= 10:
        return f"{new_num:.0f} {unit}"
    return f"{new_num:.1f} {unit}"


def simulate_notification_data(
    sub_id: str,
    noti_data: NotificationData,
    rng=random,
    dl_throughput_high: Optional[bool] = None,
) -> NotificationData:
    """
    실제 값이 변화하는 것처럼 데이터를 시뮬레이션 한다.
    NotificationItem 별 eventType 에 따라 관련 필드 값을 동적으로 변경한다.

    rng: 난수 생성기. 기본값은 전역 random 모듈(기존 동작), 재현 모드에서는
         구독별 random.Random 인스턴스(make_rng 참조).
    dl_throughput_high: None 이면 벽시계 기반 전역 토글(_dl_throughput_high)을
         쓰고, 값이 주어지면 그 값을 쓴다(재현 모드의 주기 수 기반 토글).
    """
    now = datetime.now(timezone.utc)

    for item in noti_data.notification_items:
        if item is None:
            continue
        item.time_stamp = now

        if item.event_type == "QOS_MONITORING" and item.qos_monitoring_measurement:
            qos = item.qos_monitoring_measurement

            # 공인시험 KPI 설정
            qos.dl_packet_delay = _vary_int(qos.dl_packet_delay, -1, 2, rng=rng)
            qos.ul_packet_delay = _vary_int(qos.ul_packet_delay, -1, 2, rng=rng)
            qos.dl_max_packet_delay = _vary_int(qos.dl_max_packet_delay, -2, 3, rng=rng)
            qos.ul_max_packet_delay = _vary_int(qos.ul_max_packet_delay, -2, 3, rng=rng)
            qos.dl_ave_throughput = _vary_metric_str(
                qos.dl_ave_throughput, factor=0.05, rng=rng
            )
            qos.ul_ave_throughput = _vary_metric_str(
                qos.ul_ave_throughput, factor=0.05, rng=rng
            )
            qos.packet_loss_rate = _vary_int(
                qos.packet_loss_rate, -1, 2, max_val=1000, rng=rng
            )
            qos.jitter = _vary_float(qos.jitter, 0.0, 1.5, rng=rng)

            qos.rtr_packet_delay = _vary_int(qos.rtr_packet_delay, -2, 3, rng=rng)

            qos.dl_min_packet_delay = _vary_int(qos.dl_min_packet_delay, -1, 1, rng=rng)
            qos.ul_min_packet_delay = _vary_int(qos.ul_min_packet_delay, -1, 1, rng=rng)
            qos.rtr_min_packet_delay = _vary_int(
                qos.rtr_min_packet_delay, -1, 2, rng=rng
            )

            qos.rtr_max_packet_delay = _vary_int(
                qos.rtr_max_packet_delay, -3, 4, rng=rng
            )

            qos.dl_available_bitrate = _vary_metric_str(
                qos.dl_available_bitrate, factor=0.05, rng=rng
            )
            qos.ul_available_bitrate = _vary_metric_str(
                qos.ul_available_bitrate, factor=0.05, rng=rng
            )

            qos.dl_congestion = _vary_int(
                qos.dl_congestion, -5, 10, max_val=10000, rng=rng
            )
            qos.ul_congestion = _vary_int(
                qos.ul_congestion, -5, 10, max_val=10000, rng=rng
            )

        elif (
            item.event_type == "USER_DATA_USAGE_MEASURES"
            and item.user_data_usage_measurements
        ):
            # dl_average_throughput 사전 계산: item.userDataUsageMeasurements 개수를 고려하여
            # 모든 tsm.dl_average_throughput 값의 합이 500Mbps 이하가 되도록 분배
            _high = (
                _dl_throughput_high
                if dl_throughput_high is None
                else dl_throughput_high
            )
            _eligible_tsms = []
            total_th: int = 0
            for _usage in item.user_data_usage_measurements:
                if (
                    _usage.throughput_statistics_measurement
                    and _usage.throughput_statistics_measurement.dl_average_throughput
                    is not None
                ):
                    _eligible_tsms.append(_usage.throughput_statistics_measurement)

            _num = len(_eligible_tsms)
            if _num > 0:
                if _high:
                    _total_mbps = rng.randint(500, 600)
                else:
                    _total_mbps = rng.randint(1, 100)

                # 아래 배분 루프는 tsm 하나당 최소 1Mbps 를 보장하므로, 총량이 tsm
                # 개수보다 작으면 마지막 tsm 몫이 음수가 된다. 그 값은 모델의 정규식
                # 검증(^\d+(\.\d+)? (bps|Kbps|Mbps|Gbps|Tbps)$)에 걸려 ValidationError
                # 를 내고 주기 전송 태스크를 통째로 죽인다. 총량에 하한을 둔다.
                _total_mbps = max(_total_mbps, _num)

                _props = [rng.random() for _ in range(_num)]
                _sum_prop = sum(_props)
                _assigned_values = []
                _remaining = _total_mbps
                for i in range(_num - 1):
                    _val = max(
                        1,
                        min(
                            int(round(_total_mbps * _props[i] / _sum_prop)),
                            _remaining - (_num - i - 1),
                        ),
                    )
                    _assigned_values.append(_val)
                    _remaining -= _val
                _assigned_values.append(_remaining)

                for _tsm, _val in zip(_eligible_tsms, _assigned_values):
                    if _tsm.dl_average_throughput is not None:
                        _tsm.dl_average_throughput = f"{_val} Mbps"
                    total_th += _val
            logger.info(f"[{sub_id}] set dl_average_throughput: { total_th}")

            if len(item.user_data_usage_measurements) <= 2:
                """
                이것은 wlan_performance mockup

                """
                ...

                for usage in item.user_data_usage_measurements:
                    if usage.volume_measurement:
                        vm = usage.volume_measurement
                        vm.ul_volume = _increment_volume_str(vm.ul_volume, rng=rng)
                        vm.dl_volume = _increment_volume_str(vm.dl_volume, rng=rng)
                        vm.total_volume = _increment_volume_str(
                            vm.total_volume, rng=rng
                        )
                        vm.ul_nb_of_packets = _vary_int(
                            vm.ul_nb_of_packets, 50, 300, rng=rng
                        )
                        vm.dl_nb_of_packets = _vary_int(
                            vm.dl_nb_of_packets, 50, 300, rng=rng
                        )
                        vm.total_nb_of_packets = _vary_int(
                            vm.total_nb_of_packets, 100, 600, rng=rng
                        )

                    if usage.throughput_statistics_measurement:
                        tsm = usage.throughput_statistics_measurement
                        tsm.ul_average_throughput = _vary_metric_str(
                            tsm.ul_average_throughput, rng=rng
                        )
                        # dl_average_throughput은 위에서 사전 계산하여 이미 할당됨
                        tsm.ul_peak_throughput = _vary_metric_str(
                            tsm.ul_peak_throughput, rng=rng
                        )
                        tsm.dl_peak_through_put = _vary_metric_str(
                            tsm.dl_peak_through_put, rng=rng
                        )
                        tsm.ul_average_packet_throughput = _vary_metric_str(
                            tsm.ul_average_packet_throughput, rng=rng
                        )
                        tsm.dl_average_packet_throughput = _vary_metric_str(
                            tsm.dl_average_packet_throughput, rng=rng
                        )
                        tsm.ul_peak_packet_throughput = _vary_metric_str(
                            tsm.ul_peak_packet_throughput, rng=rng
                        )
                        tsm.dl_peak_packet_throughput = _vary_metric_str(
                            tsm.dl_peak_packet_throughput, rng=rng
                        )

    return noti_data
