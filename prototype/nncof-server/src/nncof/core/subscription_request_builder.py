import os
import logging
import zlib

from typing import List, TypedDict
from datetime import datetime

from nncof.models.event_subscription import EventSubscription as NncofEventSubscription
from nncof.models.nncof_events_subscription import NncofEventsSubscription

from nsmf.models.nsmf_event_exposure import (
    NsmfEventExposure,
    EventSubscription as NsmfEventSubscription,
)
from nsmf.models.guami import Guami
from nsmf.models.plmn_id_nid import PlmnIdNid

from nsmf.models.upf_event import UpfEvent
from nsmf.models.flow_information import FlowInformation
from nsmf.models.reporting_suggestion_information import ReportingSuggestionInformation
from nsmf.models.skip_reporting_instruction import SkipReportingInstruction
from nsmf.models.time_window import TimeWindow
from nsmf.models.network_area_info import NetworkAreaInfo

from nnef.models.nef_event_filter import NefEventFilter
from nnef.models.target_ue_identification import TargetUeIdentification
from nnef.models.reporting_information import ReportingInformation
from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc, NefEventSubs
from nnef.models.network_area_info import NetworkAreaInfo as NefNetworkAreaInfo

from .supi_mapping import get_mapping_by_supi
from datetime import datetime, timezone, timedelta

from nncof.core.utils import system_info

# Create timezone (+09:00)
tz = timezone(timedelta(hours=9))

logger = logging.getLogger(__name__)


def _build_notif_uri(nf_type: str, subscription_id: str) -> str:
    s_info = system_info()
    NCOF_NOTIFICATION_BASE_URI = (
        os.getenv("NCOF_NOTIFICATION_BASE_URI")
        if os.getenv("NCOF_NOTIFICATION_BASE_URI")
        else ""
    )

    r = (
        s_info["notification_base_uri"]
        if s_info["notification_base_uri"]
        else NCOF_NOTIFICATION_BASE_URI
    )
    return f"{r}/{nf_type}/{subscription_id}"


def _generate_notif_id(type: str):
    now = datetime.now(tz)
    return f"NOTIFICATION_{type}_{now.isoformat()}"


# 감시 창(monitoring window) 기본 길이 — 요청에 monDur 가 없을 때만 사용
DEFAULT_MON_DURATION = timedelta(hours=1)


def _build_target_period(evt_req) -> TimeWindow:
    """구독 생성 시점(now)을 startTime 으로 하는 TimeWindow 를 생성한다.

    stopTime 은 요청의 monDur(절대 만료 시각)를 사용하되, monDur 가 없거나
    이미 과거이면 now + DEFAULT_MON_DURATION 으로 보정한다 (start < stop 보장).
    기존에는 start/stop 이 2026-03-01/2026-12-30 고정값이라, 대상 NF 가
    "start_time 이 과거이면 drop" 하는 경우 항상 폐기되는 문제가 있었다.
    """
    now = datetime.now(tz)
    stop = now + DEFAULT_MON_DURATION
    mon_dur = evt_req.mon_dur if evt_req is not None else None
    if mon_dur is not None:
        # tz 정보가 없는 값은 KST(+09:00) 로 간주하여 now 와 비교한다.
        m = mon_dur if mon_dur.tzinfo is not None else mon_dur.replace(tzinfo=tz)
        if m > now:
            stop = m
    return TimeWindow(startTime=now, stopTime=stop)


def _convert_flow_info_to_permit_rules(flow_info: dict) -> List[str]:
    """
    플로우 정보(dict)를 입력받아 permit in/out 규칙 리스트를 반환한다.
    TCP 프로토콜은 6으로 변환하며, 그 외 알 수 없는 프로토콜은 0으로 처리한다.
    """
    sip = flow_info.get("sip", "")
    dip = flow_info.get("dip", "")
    sp = flow_info.get("sp", "")
    dp = flow_info.get("dp", "")
    proto_str = flow_info.get("proto", "")

    # proto TCP는 6을 의미하며, 모르는 proto는 0을 할당함
    proto = 6 if proto_str == "TCP" else 0

    permit_in = f"permit in {proto} from {sip}/32 {sp} to {dip}/32 {dp}"
    permit_out = f"permit out {proto} from {dip}/32 {dp} to {sip}/32 {sp}"

    return [permit_in, permit_out]


def _generate_flow_id_from_rule(rule: str) -> int:
    """
    문자열 형태의 permit 규칙을 입력받아 고유한 숫자(Flow ID)로 변환한다.
    zlib.crc32를 사용하여 일관된 32비트 양의 정수 해시를 생성한다.
    """
    if not rule:
        return 0
    return zlib.crc32(rule.encode("utf-8")) & 0xFFFFFFFF


def _build_event_filter(
    event_subscription: NncofEventSubscription,
):
    tgt_ue = TargetUeIdentification()
    tgt_ue.any_ue_id = True
    tgt_ue.supis = getattr(event_subscription.tgt_ue, "supis", [])
    tgt_ue.inter_group_ids = getattr(event_subscription.tgt_ue, "int_group_ids", [])

    event_filter = NefEventFilter(tgtUe=tgt_ue)

    event_filter.app_ids = event_subscription.app_ids
    event_filter.loc_area = NefNetworkAreaInfo.from_dict(
        event_subscription.network_area.to_dict()
        if event_subscription.network_area
        else {}
    )

    return event_filter


def _build_traffic_filter(supi: str, use_any_ue: bool = False) -> List[FlowInformation]:

    supi_info = get_mapping_by_supi(supi)

    if supi_info is not None and supi_info["flowInfo"] is not None:
        permit_rules = _convert_flow_info_to_permit_rules(supi_info["flowInfo"])
    else:
        permit_rules = ["permit in ip from any to any", "permit in ip from any to any"]

    if use_any_ue:
        permit_rules = ["permit in ip from any to any", "permit in ip from any to any"]

    tf_uplink = FlowInformation()
    tf_uplink.flow_description = permit_rules[0]
    tf_uplink.pack_filt_id = str(_generate_flow_id_from_rule(permit_rules[0]))
    tf_uplink.packet_filter_usage = False
    tf_uplink.flow_direction = "UPLINK"

    tf_downlink = FlowInformation()
    tf_downlink.flow_description = permit_rules[1]
    tf_downlink.pack_filt_id = str(_generate_flow_id_from_rule(permit_rules[1]))
    tf_downlink.packet_filter_usage = False
    tf_downlink.flow_direction = "DOWNLINK"
    return [tf_uplink, tf_downlink]


def _build_reporting_info(nncof_events_subscription: NncofEventsSubscription):
    reporting_info = (
        ReportingInformation.from_dict(nncof_events_subscription.evt_req.to_dict())
        if nncof_events_subscription.evt_req is not None
        else None
    )
    return reporting_info


def _handle_cell_power_ctrl(
    subscription_id: str,
    nncof_events_subscription: NncofEventsSubscription,
    event_subscription: NncofEventSubscription,
):

    event_sub_rf_signal = NefEventSubs(event="_RF_SIGNAL")
    event_sub_power_energy_consumption = NefEventSubs(event="_POWER_ENERGY_CONSUMPTION")

    reporting_info = _build_reporting_info(nncof_events_subscription)

    locArea = (
        NefNetworkAreaInfo.from_dict(event_subscription.network_area.to_dict())
        if event_subscription.network_area is not None
        else None
    )

    tgt_ue = (
        TargetUeIdentification.from_dict(event_subscription.tgt_ue.to_dict())
        if event_subscription.tgt_ue is not None
        else None
    )

    if tgt_ue is not None:
        nef_event_filter_obj = NefEventFilter(
            tgtUe=tgt_ue, appIds=event_subscription.app_ids, locArea=locArea
        )
        nef_event_filter_obj2 = NefEventFilter(
            tgtUe=tgt_ue, appIds=event_subscription.app_ids, locArea=locArea
        )
        event_sub_rf_signal.event_filter = nef_event_filter_obj2
        event_sub_power_energy_consumption.event_filter = nef_event_filter_obj
        event_sub_power_energy_consumption.event_rep_info = reporting_info
        event_sub_rf_signal.event_rep_info = reporting_info

    nef_subscription = NefEventExposureSubsc(
        notifId=_generate_notif_id("ricf"),
        notifUri=_build_notif_uri("ricf", subscription_id),
        eventsSubs=[event_sub_rf_signal, event_sub_power_energy_consumption],
    )

    nef_subscription.data_acc_prof_id = "dap-002"
    nef_subscription.events_rep_info = reporting_info
    nef_subscription.supp_feat = "FF"

    return [
        {"target": "ricf", "subscription": nef_subscription},
    ]


def _fill_nsmf_event_subscription(
    subscription_id: str,
    nncof_events_subscription: NncofEventsSubscription,
    event_subscription: NncofEventSubscription,
    nsmf_subscription: NsmfEventExposure,
):
    """
    nsmf_subscription 의 공통 부분을 채운다.
    """

    evt_req = (
        nncof_events_subscription.evt_req
        if nncof_events_subscription is not None
        else ReportingInformation(repPeriod=50)
    )

    nsmf_subscription.notif_id = _generate_notif_id("upf")
    nsmf_subscription.notif_uri = _build_notif_uri("upf", subscription_id)

    nsmf_subscription.nf_id = "ncof-uuid-001"
    nsmf_subscription.notif_method = "PERIODIC"
    if evt_req is not None:
        nsmf_subscription.rep_period = evt_req.rep_period
        nsmf_subscription.max_report_nbr = evt_req.max_report_nbr
        nsmf_subscription.expiry = evt_req.mon_dur
    nsmf_subscription.imme_rep = False
    nsmf_subscription.samp_ratio = 100
    nsmf_subscription.servive_name = "nsmf-event_exposure"
    nsmf_subscription.supported_features = "FF"
    nsmf_subscription.def_qos_supp = False
    nsmf_subscription.qos_mon_pending = False
    nsmf_subscription.udr_restart_ind = False
    nsmf_subscription.any_ue_ind = False
    nsmf_subscription.group_id = "00000001-001-01-0001"
    nsmf_subscription.dnn = "6g-i2p.etri.re.kr"
    nsmf_subscription.upf_id = "upf-001"

    # 속성들이 존재하고 리스트가 비어있지 않은 경우에만 할당
    if (na := event_subscription.network_area) and (nodes := na.g_ran_node_ids):
        plmn_id_ = nodes[0].plmn_id
    else:
        plmn_id_ = None  # 혹은 기본값 설정

    # plmn_id_ = event_subscription.network_area.g_ran_node_ids[0].plmn_id
    if plmn_id_ is not None:
        plmn_id = PlmnIdNid(mcc=plmn_id_.mcc, mnc=plmn_id_.mnc)
        nsmf_subscription.guami = Guami(plmnId=plmn_id, amfId="000001")


def _handle_service_experience(
    subscription_id: str,
    nncof_events_subscription: NncofEventsSubscription,
    event_subscription: NncofEventSubscription,
):

    # QOS_MONITORING

    evt_sub_smf = NsmfEventSubscription(event="UPF_EVENT")

    # evt_sub_smf.network_area
    evt_sub_smf.target_period = _build_target_period(nncof_events_subscription.evt_req)

    if event_subscription.network_area is not None:

        evt_sub_smf.network_area = NetworkAreaInfo.from_dict(
            event_subscription.network_area.to_dict()
        )

    evt_sub_smf.transac_disp_ind = False

    supis = (event_subscription.tgt_ue.supis if event_subscription.tgt_ue else []) or []
    app_ids = event_subscription.app_ids or []
    pdu_ses_infos = event_subscription.pdu_ses_infos or []

    upf_events = []
    # supi 개수만큼 qos 모니터링 객체 생성
    for index, supi in enumerate(supis):
        qos_monitoring = UpfEvent(type="QOS_MONITORING")
        qos_monitoring.immediate_flag = False

        if index < len(app_ids):
            qos_monitoring.app_ids = [app_ids[index]]

        qos_monitoring.traffic_filters = _build_traffic_filter(supi)
        qos_monitoring.granularity_of_measurement = "PER_FLOW"
        qos_monitoring.reporting_suggestion_info = ReportingSuggestionInformation(
            reportingUrgency="DELAY_TOLERANT", reportingTimeInfo=10
        )
        qos_monitoring.ip_domain = "6g-i2p.etri.re.kr"
        qos_monitoring.remaining_data_reports = "DISCARD"
        qos_monitoring.skip_reporting_instruction = SkipReportingInstruction(
            skipReportCond=["SKIP_OUTSIDE_VALIDITY_TIME"]
        )
        qos_monitoring.incl_rat_type = True

        # pdu_ses_infos 안전한 접근
        if (
            index < len(pdu_ses_infos)
            and (pdu_info := pdu_ses_infos[index])
            and pdu_info.access_types
        ):
            rat_value = "NR" if pdu_info.access_types[0] == "3GPP_ACCESS" else "WLAN"
            qos_monitoring.rat_type_list = [rat_value]
        else:
            # 기본값 설정 또는 정보 부재 시 처리
            qos_monitoring.rat_type_list = ["NR"]

        upf_events.append(qos_monitoring)

    # USER_DATA_USAGE_MEASURES

    udum = UpfEvent(type="USER_DATA_USAGE_MEASURES")
    udum.immediate_flag = False
    udum.measurement_types = [
        "APPLICATION_RELATED_INFO",
        "THROUGHPUT_MEASUREMENT",
        "VOLUME_MEASUREMENT",
    ]
    udum.app_ids = event_subscription.app_ids
    traffic_filters = []
    for index, supi in enumerate(supis):
        traffic_filters += _build_traffic_filter(supi)

    udum.traffic_filters = traffic_filters

    udum.granularity_of_measurement = "PEF_FLOW"
    udum.reporting_suggestion_info = ReportingSuggestionInformation(
        reportingUrgency="DELAY_TOLERANT", reportingTimeInfo=10
    )
    udum.incl_rat_type = True

    pdu_ses_infos = (
        event_subscription.pdu_ses_infos if event_subscription.pdu_ses_infos else []
    )

    # rat_value = "NR" if pdu_session_info.access_types[0] == "3GPP_ACCESS" else "WLAN"
    # qos_monitoring.rat_type_list = [rat_value]

    rat_types = [
        rat
        for info in pdu_ses_infos
        for rat in (
            ["NR"] * 2
            if info and info.access_types and info.access_types[0] == "3GPP_ACCESS"
            else ["WLAN"] * 2
        )
    ]

    udum.rat_type_list = rat_types

    upf_events.append(udum)

    evt_sub_smf.upf_events = upf_events

    nsmf_subscription = NsmfEventExposure(
        notifId=_generate_notif_id("upf"),
        notifUri=_build_notif_uri("smf", subscription_id),
        eventSubs=[evt_sub_smf],
    )

    # nsmf_subscription.notif_id = ""
    # nsmf_subscription.notif_uri = ""

    # evt_req = (
    #     nncof_events_subscription.evt_req
    #     if nncof_events_subscription is not None
    #     else ReportingInformation(repPeriod=60)
    # )

    # nsmf_subscription.nf_id = "ncof-uuid-001"
    # nsmf_subscription.notif_method = "PERIODIC"
    # if evt_req is not None:
    #     nsmf_subscription.rep_period = evt_req.rep_period
    #     nsmf_subscription.max_report_nbr = evt_req.max_report_nbr
    #     nsmf_subscription.expiry = evt_req.mon_dur
    # nsmf_subscription.imme_rep = False
    # nsmf_subscription.samp_ratio = 100
    # nsmf_subscription.servive_name = "nsmf-event_exposure"
    # nsmf_subscription.supported_features = "FF"
    # nsmf_subscription.def_qos_supp = False
    # nsmf_subscription.qos_mon_pending = False
    # nsmf_subscription.udr_restart_ind = False
    # nsmf_subscription.any_ue_ind = False
    # nsmf_subscription.group_id = "00000001-001-01-0001"
    # nsmf_subscription.dnn = "6g-i2p.etri.re.kr"
    # nsmf_subscription.upf_id = "upf-001"

    _fill_nsmf_event_subscription(
        subscription_id,
        nncof_events_subscription,
        event_subscription,
        nsmf_subscription,
    )

    # ------END OF 3 PRIME -----
    # rprint(nsmf_subscription)

    #
    # PERF_DATA RAN (RICF)
    #
    evt_sub_perf_data_af = NefEventSubs(event="PERF_DATA")

    event_filter = _build_event_filter(event_subscription)
    evt_sub_perf_data_af.event_filter = event_filter

    reporting_info = (
        ReportingInformation.from_dict(nncof_events_subscription.evt_req.to_dict())
        if nncof_events_subscription.evt_req is not None
        else None
    )

    evt_sub_perf_data_af.event_rep_info = reporting_info

    # CN AF로 보낼 구독 요청
    af_event_exposure = NefEventExposureSubsc(
        # notifId="", notifUri="",
        notifId=_generate_notif_id("af"),
        notifUri=_build_notif_uri("af", subscription_id),
        eventsSubs=[evt_sub_perf_data_af],
    )

    #
    # PERF_DATA CN(AF)
    #
    evt_sub_perf_data_ricf = NefEventSubs(event="PERF_DATA")

    event_filter = _build_event_filter(event_subscription)
    evt_sub_perf_data_ricf.event_filter = event_filter
    evt_sub_perf_data_ricf.event_rep_info = reporting_info

    # RAN RICF로 보낼 구독 요청
    ricf_event_exposure = NefEventExposureSubsc(
        # notifId="",
        # notifUri="",
        notifId=_generate_notif_id("ricf"),
        notifUri=_build_notif_uri("ricf", subscription_id),
        eventsSubs=[evt_sub_perf_data_ricf],
    )

    af_event_exposure.events_rep_info = reporting_info
    ricf_event_exposure.events_rep_info = reporting_info
    af_event_exposure.supp_feat = "FF"

    return [
        {"target": "smf", "subscription": nsmf_subscription},
        {"target": "af", "subscription": af_event_exposure},
        {"target": "ricf", "subscription": ricf_event_exposure},
    ]


def _handle_e2e_data_vol(
    subscription_id: str,
    nncof_events_subscription: NncofEventsSubscription,
    event_subscription: NncofEventSubscription,
):
    #
    # DISPERSION: ---> AF
    #
    evt_sub_perf_data_af = NefEventSubs(event="DISPERSION")

    event_filter = _build_event_filter(event_subscription)
    evt_sub_perf_data_af.event_filter = event_filter

    reporting_info = _build_reporting_info(nncof_events_subscription)

    evt_sub_perf_data_af.event_rep_info = reporting_info

    nef_subscription = NefEventExposureSubsc(
        notifId=_generate_notif_id("af"),
        notifUri=_build_notif_uri("af", subscription_id),
        eventsSubs=[evt_sub_perf_data_af],
    )

    nef_subscription.data_acc_prof_id = "dap-002"
    nef_subscription.events_rep_info = reporting_info
    nef_subscription.supp_feat = "FF"

    return [{"target": "af", "subscription": nef_subscription}]


def _handle_ricf_wlan_performance(
    subscription_id: str,
    nncof_events_subscription: NncofEventsSubscription,
    event_subscription: NncofEventSubscription,
):
    """ """

    upf_events = []

    udum = UpfEvent(type="USER_DATA_USAGE_MEASURES")
    udum.immediate_flag = False
    udum.measurement_types = [
        "THROUGHPUT_MEASUREMENT",
        "VOLUME_MEASUREMENT",
    ]

    supis = (event_subscription.tgt_ue.supis if event_subscription.tgt_ue else []) or []

    # supi 개수만큼 qos 모니터링 객체 생성
    for index, supi in enumerate(supis):
        udum.traffic_filters = _build_traffic_filter(supi, True)

    udum.granularity_of_measurement = "PEF_FLOW"

    udum.reporting_suggestion_info = ReportingSuggestionInformation(
        reportingUrgency="DELAY_TOLERANT", reportingTimeInfo=10
    )
    # qos_monitoring.ip_domain = "6g-i2p.etri.re.kr"
    udum.remaining_data_reports = "DISCARD"
    udum.skip_reporting_instruction = SkipReportingInstruction(
        skipReportCond=["SKIP_OUTSIDE_VALIDITY_TIME"]
    )

    udum.incl_rat_type = False

    upf_events.append(udum)

    evt_sub_smf = NsmfEventSubscription(event="UPF_EVENT", upfEvents=upf_events)

    evt_sub_smf.target_period = _build_target_period(nncof_events_subscription.evt_req)

    if event_subscription.network_area is not None:
        evt_sub_smf.network_area = NetworkAreaInfo.from_dict(
            event_subscription.network_area.to_dict()
        )

    evt_sub_smf.transac_disp_ind = True

    nsmf_subscription = NsmfEventExposure(
        notifId="", notifUri="", eventSubs=[evt_sub_smf]
    )

    _fill_nsmf_event_subscription(
        subscription_id,
        nncof_events_subscription,
        event_subscription,
        nsmf_subscription,
    )

    return [{"target": "smf", "subscription": nsmf_subscription}]


def _handle_qos_policy_assist(
    subscription_id: str,
    nncof_events_subscription: NncofEventsSubscription,
    event_subscription: NncofEventSubscription,
):
    return []


# 메시지 빌더 매핑 테이블
SUBSCRIPTIOS_BUILIN_BUILDERS = {
    "_CELL_POWER_CTRL": _handle_cell_power_ctrl,
    "SERVICE_EXPERIENCE": _handle_service_experience,
    "E2E_DATA_VOL_TRANS_TIME": _handle_e2e_data_vol,
    "WLAN_PERFORMANCE": _handle_ricf_wlan_performance,
    "QOS_POLICY_ASSIST": _handle_qos_policy_assist,
}


class ExternalSubscriptionRequest(TypedDict):
    """외부 NF로 전송할 구독 요청을 표현하는 타입."""

    target: str
    subscription: NsmfEventExposure | NefEventExposureSubsc
    external_sub_id: str | None


def build_subscription_requests(
    subscription_id: str, nncof_events_subscription: NncofEventsSubscription
) -> List[ExternalSubscriptionRequest]:
    """
    구독요청으로 부터 하위 구독요청을 생성하는 함수이다.
    각 event type 별 전용 빌더를 사용하여 데이터 수집 대상 NF로 보낼 구독요청을 생성한다.
    """
    requests: List[ExternalSubscriptionRequest] = []
    for event_subscription in nncof_events_subscription.event_subscriptions:
        builde_subscription_request = SUBSCRIPTIOS_BUILIN_BUILDERS.get(
            event_subscription.event
        )
        if builde_subscription_request is None:
            logging.warning(f"Unhandled event: {event_subscription.event}")
            continue

        requests.extend(
            builde_subscription_request(
                subscription_id,
                nncof_events_subscription,
                event_subscription,
            )
        )

    return requests
