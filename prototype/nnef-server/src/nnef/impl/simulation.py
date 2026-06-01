from typing import Dict
import asyncio
import random
from typing import Dict
import uuid
from datetime import datetime, timezone
import logging

from nnef.models.power_energy_cons_data import PowerEnergyConsData
from rich.pretty import pprint

from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc
from nnef.models.nef_event_exposure_notif import NefEventExposureNotif

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from . import utils
from . import simulation


from .ncof_callback_impl import NCOFEventNotificationImpl

logger = logging.getLogger(__name__)

subscriptions: Dict[str, dict] = {}


def _power_energy_cons_data_deepsleep():
    power_energy_cons_data = PowerEnergyConsData()
    power_energy_cons_data.start_time = datetime.now(timezone.utc)
    power_energy_cons_data.duration = 60
    power_energy_cons_data.power = "0mW"
    power_energy_cons_data.min_power = "0mW"
    power_energy_cons_data.peak_power = "0mW"
    power_energy_cons_data.energy = "0.0J"
    power_energy_cons_data.power_state = "DEEP_SLEEP"
    return power_energy_cons_data


async def periodic_notification_sender(sub_id: str, interval_seconds: int):
    while True:
        sub = subscriptions.get(sub_id)
        if sub is None:
            logger.warning(f"[{sub_id}] Subscription not found. Stopping sender.")
            break
        event_subscription: NefEventExposureSubsc = sub["event_subscription"]
        event_notification: NefEventExposureNotif = sub["event_notification"]

        logger.info(f"[{sub_id}] {event_notification.notif_id}")
        # expiry = nsmf_event_exposure.mon
        events_rep_info = getattr(event_subscription, "events_rep_info", None)
        mon_dur = getattr(events_rep_info, "mon_dur", None)
        if mon_dur:
            if datetime.now(timezone.utc) >= mon_dur:
                logger.warning(
                    f"[{sub_id}] Expiry time reached. Stopping notification sender."
                )
                del subscriptions[sub_id]
                break

        notif_uri = event_subscription.notif_uri

        logger.info(f"interval_seconds: {interval_seconds}")
        await asyncio.sleep(interval_seconds)

        logger.info(
            f"cell_power_state changed: {NCOFEventNotificationImpl.cell_power_state}"
        )
        simulation_notification_data(event_notification)

        # simulate DEEP_SLEEP state
        if NCOFEventNotificationImpl.cell_power_state == "DEEP_SLEEP":
            for event_notif in event_notification.event_notifs:
                if event_notif.event == "_POWER_ENERGY_CONSUMPTION":
                    if event_notif.power_energy_consumption_infos is not None:
                        event_notif.power_energy_consumption_infos[
                            1
                        ].power_energy_cons_data = _power_energy_cons_data_deepsleep()
        logger.info(f"[{sub_id}] 💡[Notification]---> [NCOF]")
        await utils.notify(
            sub_id, notif_uri, event_notification.model_dump(mode="json")
        )


def _randomize_perf_data(pd) -> None:
    pd.pdb = random.randint(5, 50)
    pd.pdb_dl = random.randint(3, 30)
    pd.max_pdb_ul = random.randint(10, 100)
    pd.max_pdb_dl = random.randint(10, 100)

    pd.plr = random.randint(0, 50)  # 0.0% ~ 5.0%
    pd.plr_dl = random.randint(0, 30)
    pd.max_plr_ul = random.randint(0, 100)
    pd.max_plr_dl = random.randint(0, 100)

    pd.thrput_ul = f"{random.randint(10, 100)} Mbps"
    pd.max_thrput_ul = f"{random.randint(100, 500)} Mbps"
    pd.min_thrput_ul = f"{random.randint(5, 50)} Mbps"
    pd.thrput_dl = f"{random.randint(50, 300)} Mbps"
    pd.max_thrput_dl = f"{random.randint(300, 1000)} Mbps"
    pd.min_thrput_dl = f"{random.randint(20, 200)} Mbps"

    pd.min_rtt = random.randint(1, 20)
    pd.max_rtt = random.randint(10, 100)
    pd.delay_ul = random.randint(1, 20)
    pd.min_delay_ul = random.randint(1, 10)
    pd.max_delay_ul = random.randint(10, 50)
    pd.jitter = round(random.uniform(0.0, 10.0), 1)


def _randomize_dispersion_data(dc) -> None:
    if dc.data_usage is not None:
        dc.data_usage.duration = random.randint(30, 300)
        dc.data_usage.total_volume = random.randint(5_000_000_000, 50_000_000_000)
        dc.data_usage.downlink_volume = random.randint(3_000_000_000, 40_000_000_000)
        dc.data_usage.uplink_volume = random.randint(1_000_000_000, 10_000_000_000)


def _randomize_rf_signal_data(rs_data) -> None:
    if rs_data.ref_signal_measurements:
        for m in rs_data.ref_signal_measurements:
            m.rsrp = f"{random.randint(60, 100)}dBm"
            m.rsrq = f"{random.randint(-20, -5)}dB"
            m.sinr = f"{random.randint(5, 25)}dB"
            m.bler = round(random.uniform(0.9, 1.0), 3)
            m.connectivity = random.choice(["EXCELLENT", "GOOD", "MEDIUM", "WEAK"])


def _randomize_power_energy_cons_data(pec_data) -> None:
    pec_data.duration = random.randint(30, 300)
    pec_data.power = f"{random.randint(5, 50)}mW"
    pec_data.min_power = f"{random.randint(0, 10)}mW"
    pec_data.peak_power = f"{random.randint(30, 100)}mW"
    pec_data.energy = f"{round(random.uniform(0.5, 5.0), 1)}J"
    pec_data.power_state = random.choice(
        ["ACTIVE", "ACTIVE_UL", "ACTIVE_DL", "MICRO_SLEEP", "LIGHT_SLEEP", "DEEP_SLEEP"]
    )


def simulation_notification_data(
    noti_data: NefEventExposureNotif,
) -> NefEventExposureNotif:
    """
    실제 값이 변화하는 것처럼 데이터를 시뮬레이션 한다.
    NefEventNotification 별 event 에 따라 관련 필드 값을 동적으로 변경한다.

    - PERF_DATA             : perfDataInfos[*].perfData 의 모든 메트릭을 랜덤화
    - DISPERSION            : dispersionInfos[*].dataUsage 의 볼륨/시간을 랜덤화
    - _RF_SIGNAL            : rfSignalInfos[*].rfSignalData.refSignalMeasurements
                                (rsrp, rsrq, sinr, bler, connectivity) 랜덤화
    - _POWER_ENERGY_CONSUMPTION : powerEnergyConsInfos[*].powerEnergyConsData
                                (power, energy, powerState 등) 랜덤화
    """
    now = datetime.now(timezone.utc)

    for event_notif in noti_data.event_notifs:
        event_notif.time_stamp = now

        if event_notif.event == "PERF_DATA" and event_notif.perf_data_infos:
            for perf_info in event_notif.perf_data_infos:
                perf_info.time_stamp = now
                _randomize_perf_data(perf_info.perf_data)

        elif event_notif.event == "DISPERSION" and event_notif.dispersion_infos:
            for disp_info in event_notif.dispersion_infos:
                disp_info.time_stamp = now
                _randomize_dispersion_data(disp_info)

        elif event_notif.event == "_RF_SIGNAL" and event_notif.rf_signal_infos:
            for rf_info in event_notif.rf_signal_infos:
                if rf_info.rf_signal_data:
                    _randomize_rf_signal_data(rf_info.rf_signal_data)

        elif (
            event_notif.event == "_POWER_ENERGY_CONSUMPTION"
            and event_notif.power_energy_consumption_infos
        ):
            for pec_info in event_notif.power_energy_consumption_infos:
                if pec_info.power_energy_cons_data:
                    _randomize_power_energy_cons_data(pec_info.power_energy_cons_data)

    return noti_data


async def handle_subcription_request(
    template_file: str, nef_event_exposure_subsc: NefEventExposureSubsc
) -> JSONResponse:

    payload = utils.load_json(template_file)
    nef_event_notification = NefEventExposureNotif.from_dict(payload)

    sub_id = str(uuid.uuid4())
    # nef_event_exposure_subsc.sub_id = sub_id
    nef_event_notification.notif_id = nef_event_exposure_subsc.notif_id
    print("notifId:", nef_event_exposure_subsc.notif_id)
    subscriptions[sub_id] = {
        "event_subscription": nef_event_exposure_subsc,
        "event_notification": nef_event_notification,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    rep_period = (
        getattr(nef_event_exposure_subsc.events_rep_info, "rep_period", None) or 60
    )

    asyncio.create_task(
        simulation.periodic_notification_sender(sub_id, interval_seconds=rep_period)
    )

    return JSONResponse(
        content=jsonable_encoder(nef_event_exposure_subsc),
        headers={"Subscription-ID": sub_id},
        status_code=201,
    )


# payload = utils.load_json(
#     "13p_d_NncofEventsSubscriptionNotification_from RICF_to_NCOF_v1.0.json"
# )
# nef_event_notification = NefEventExposureNotif.from_dict(payload)
# pprint(nef_event_notification.event_notifs[1].power_energy_consumption_infos)
