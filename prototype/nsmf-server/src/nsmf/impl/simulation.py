import random
import re
import asyncio
from typing import Optional

from datetime import datetime, timezone

import logging

logger = logging.getLogger(__name__)

from nupf.models.notification_data import NotificationData

_dl_throughput_high = True


async def start_dl_throughput_toggle(interval_seconds: int = 10):
    """
    서버 시작시 호출되어 주기적으로 _dl_throughput_high 값을 토글한다.
    """
    global _dl_throughput_high
    while True:
        await asyncio.sleep(interval_seconds)
        logger.info(
            f"💢 Toggle dl_throughput: { 'High' if _dl_throughput_high else 'Low'}"
        )
        _dl_throughput_high = not _dl_throughput_high


def _vary_int(
    value: Optional[int], min_delta: int, max_delta: int, max_val: Optional[int] = None
) -> Optional[int]:
    if value is None:
        return None
    new_val = value + random.randint(min_delta, max_delta)
    if max_val is not None:
        new_val = min(new_val, max_val)
    return max(0, new_val)


def _vary_float(
    value: Optional[float], min_delta: float, max_delta: float
) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, round(value + random.uniform(min_delta, max_delta), 2))


def _parse_number_unit(text: str):
    """Parse '150 Mbps' -> (150.0, 'Mbps')"""
    match = re.match(r"([\d.]+)\s*(.+)", text)
    if match:
        return float(match.group(1)), match.group(2).strip()
    return None, text


def _vary_metric_str(value: Optional[str], factor: float = 0.1) -> Optional[str]:
    """Vary a metric string like '150 Mbps' by +/- factor%"""
    if value is None:
        return None
    num, unit = _parse_number_unit(value)
    if num is None:
        return value
    delta = num * random.uniform(-factor, factor)
    new_num = max(0.0, num + delta)
    if new_num >= 10:
        return f"{new_num:.0f} {unit}"
    return f"{new_num:.1f} {unit}"


def _increment_volume_str(
    value: Optional[str], inc_range: tuple[float, float] = (0.1, 0.5)
) -> Optional[str]:
    """Increment a volume string like '3 GB' by a random amount"""
    if value is None:
        return None
    num, unit = _parse_number_unit(value)
    if num is None:
        return value
    inc = random.uniform(*inc_range)
    new_num = num + inc
    if new_num >= 10:
        return f"{new_num:.0f} {unit}"
    return f"{new_num:.1f} {unit}"


def simulate_notification_data(
    sub_id: str, noti_data: NotificationData
) -> NotificationData:
    """
    실제 값이 변화하는 것처럼 데이터를 시뮬레이션 한다.
    NotificationItem 별 eventType 에 따라 관련 필드 값을 동적으로 변경한다.
    """
    now = datetime.now(timezone.utc)

    for item in noti_data.notification_items:
        if item is None:
            continue
        item.time_stamp = now

        if item.event_type == "QOS_MONITORING" and item.qos_monitoring_measurement:
            qos = item.qos_monitoring_measurement

            qos.dl_packet_delay = _vary_int(qos.dl_packet_delay, -1, 2)
            qos.ul_packet_delay = _vary_int(qos.ul_packet_delay, -1, 2)
            qos.rtr_packet_delay = _vary_int(qos.rtr_packet_delay, -2, 3)

            qos.dl_min_packet_delay = _vary_int(qos.dl_min_packet_delay, -1, 1)
            qos.ul_min_packet_delay = _vary_int(qos.ul_min_packet_delay, -1, 1)
            qos.rtr_min_packet_delay = _vary_int(qos.rtr_min_packet_delay, -1, 2)

            qos.dl_max_packet_delay = _vary_int(qos.dl_max_packet_delay, -2, 3)
            qos.ul_max_packet_delay = _vary_int(qos.ul_max_packet_delay, -2, 3)
            qos.rtr_max_packet_delay = _vary_int(qos.rtr_max_packet_delay, -3, 4)

            qos.packet_loss_rate = _vary_int(qos.packet_loss_rate, -1, 2, max_val=1000)

            qos.jitter = _vary_float(qos.jitter, 0.0, 1.5)

            qos.dl_ave_throughput = _vary_metric_str(qos.dl_ave_throughput, factor=0.05)
            qos.ul_ave_throughput = _vary_metric_str(qos.ul_ave_throughput, factor=0.05)
            qos.dl_available_bitrate = _vary_metric_str(
                qos.dl_available_bitrate, factor=0.05
            )
            qos.ul_available_bitrate = _vary_metric_str(
                qos.ul_available_bitrate, factor=0.05
            )

            qos.dl_congestion = _vary_int(qos.dl_congestion, -5, 10, max_val=10000)
            qos.ul_congestion = _vary_int(qos.ul_congestion, -5, 10, max_val=10000)

        elif (
            item.event_type == "USER_DATA_USAGE_MEASURES"
            and item.user_data_usage_measurements
        ):
            # dl_average_throughput 사전 계산: item.userDataUsageMeasurements 개수를 고려하여
            # 모든 tsm.dl_average_throughput 값의 합이 500Mbps 이하가 되도록 분배
            global _dl_throughput_high
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
                if _dl_throughput_high:
                    _total_mbps = random.randint(500, 600)
                else:
                    _total_mbps = random.randint(1, 100)

                _props = [random.random() for _ in range(_num)]
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
                        vm.ul_volume = _increment_volume_str(vm.ul_volume)
                        vm.dl_volume = _increment_volume_str(vm.dl_volume)
                        vm.total_volume = _increment_volume_str(vm.total_volume)
                        vm.ul_nb_of_packets = _vary_int(vm.ul_nb_of_packets, 50, 300)
                        vm.dl_nb_of_packets = _vary_int(vm.dl_nb_of_packets, 50, 300)
                        vm.total_nb_of_packets = _vary_int(
                            vm.total_nb_of_packets, 100, 600
                        )

                    if usage.throughput_statistics_measurement:
                        tsm = usage.throughput_statistics_measurement
                        tsm.ul_average_throughput = _vary_metric_str(
                            tsm.ul_average_throughput
                        )
                        # dl_average_throughput은 위에서 사전 계산하여 이미 할당됨
                        tsm.ul_peak_throughput = _vary_metric_str(
                            tsm.ul_peak_throughput
                        )
                        tsm.dl_peak_through_put = _vary_metric_str(
                            tsm.dl_peak_through_put
                        )
                        tsm.ul_average_packet_throughput = _vary_metric_str(
                            tsm.ul_average_packet_throughput
                        )
                        tsm.dl_average_packet_throughput = _vary_metric_str(
                            tsm.dl_average_packet_throughput
                        )
                        tsm.ul_peak_packet_throughput = _vary_metric_str(
                            tsm.ul_peak_packet_throughput
                        )
                        tsm.dl_peak_packet_throughput = _vary_metric_str(
                            tsm.dl_peak_packet_throughput
                        )

    return noti_data
