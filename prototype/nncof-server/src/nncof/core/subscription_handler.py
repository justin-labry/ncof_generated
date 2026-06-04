import logging
import asyncio
import json
import httpx
import uuid

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Final, List, Literal, Optional

from rich.pretty import pprint as rprint
from fastapi.encoders import jsonable_encoder

from nncof.models.nncof_events_subscription import NncofEventsSubscription
from nncof.models.nncof_events_subscription_notification import (
    NncofEventsSubscriptionNotification,
)
from nnef.models.nef_event_exposure_notif import NefEventExposureNotif
from nsmf.models.nsmf_event_exposure import NsmfEventExposure

from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc

from nupf.models.notification_data import NotificationData

from .subscription_request_builder import build_subscription_requests
from .nrf import nrf
from .subscription_request_builder import ExternalSubscriptionRequest
from .websocket_manager import broadcast_web_message

from .data_store import NotificationDataStore
from .gnb2_rule_engine import Gnb2RuleEngine

logger = logging.getLogger(__name__)


def _now_iso_kst() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class SubscriptionHandler:
    """
    SubscriptionHandler 는 NF(PCF, RICF)로부터의 개별 구독 요청을 처리한다.
    """

    def __init__(
        self,
        subscription_id: str,
        subscription: NncofEventsSubscription,
        max_data_entries: int = 100,
        relation_manager: Any = None,
    ):
        self.subscription_id = subscription_id
        self.subscription = subscription
        self._relation_manager = relation_manager
        self.notif_data_store = NotificationDataStore()
        self.control_data_store = NotificationDataStore()
        self.is_running = False
        self._task: asyncio.Task | None = None
        # 외부 NF로 보낸 구독 정보를 저장 (target_nf, external_sub_id, req_body)
        self.external_subscriptions: List[ExternalSubscriptionRequest] = []
        # HTTP 연결 풀 재사용을 위한 공유 클라이언트
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(5.0))
        self.rule_engine = Gnb2RuleEngine()

    def _get_source_nf_type(self) -> Literal["PCF", "RICF"] | None:
        """
        소스 NF 타입을 반환한다. 즉, 구독요청을 보낸 NF 타입을 반환한다.
        """
        if not self.subscription.event_subscriptions:
            return None

        mapping: Final[dict[str, Literal["PCF", "RICF"]]] = {
            "QOS_POLICY_ASSIST": "PCF",
            "_CELL_POWER_CTRL": "RICF",
        }

        for sub in self.subscription.event_subscriptions:
            if sub.event in mapping:
                return mapping[sub.event]

        return None

    async def _send_external_subscription(
        self, target: str, req_body: NsmfEventExposure | NefEventExposureSubsc
    ) -> Optional[str]:
        """
        데이터 수집을 위한 NF로 구독 요청을 전송하고, 해당 NF가 생성한 구독 ID를 반환한다.
        """
        logger.info(f"[{self.subscription_id}] send subscription request to [{target}]")

        nf_uri = nrf.get_nf_uri(target)

        if not nf_uri:
            logger.warning(
                f"[{self.subscription_id}] NF URI를 찾을 수 없음: {target}. 기본 경로 사용 시도."
            )
            nf_uri = f"http://{target.lower()}.local"

        subscription_url = f"{nf_uri}/subscriptions"
        logger.info(f"[{self.subscription_id}] Sending POST to: {subscription_url}")
        sub_id = f"ext-{target.lower()}-{str(uuid.uuid4())[:8]}"
        try:
            # Pydantic 모델을 JSON 직렬화 가능한 딕셔너리로 변환
            json_data = jsonable_encoder(req_body)

            response = await self._client.post(subscription_url, json=json_data)
            if response.status_code in (200, 201):
                resp_json = response.json()
                # 응답 바디에서 ID 추출 (subscriptionId 또는 subId)
                sub_id = resp_json.get("subscriptionId") or resp_json.get("subId")

                if not sub_id and "Subscription-ID" in response.headers:
                    # 헤더에서 ID 추출
                    sub_id = response.headers["Subscription-ID"]

                if sub_id:
                    logger.info(
                        f"[{self.subscription_id}] {target.upper()} 🔆구독 성공. ID: {sub_id}"
                    )
                    return sub_id

            logger.warning(
                f"[{self.subscription_id}] {target.upper()}로부터 ID를 획득하지 못함 (Status: {response.status_code})."
            )
        except Exception as e:
            logger.error(
                f"[{self.subscription_id}] {target.upper()} 연결 중 오류 발생: {e}"
            )
            return None

        # 실제 NF가 없거나 요청 실패 시 PoC 시뮬레이션을 위해 임의의 ID 반환
        # mock_id = f"ext-{target.lower()}-{str(uuid.uuid4())[:8]}"
        logger.info(f"[{self.subscription_id}] 시뮬레이션용 Mock ID 생성: {sub_id}")
        return sub_id

    async def _send_external_unsubscription(self, target: str, external_sub_id: str):
        """
        다른 NF로 구독 해지 요청을 전송한다.
        """
        logger.info(
            f"[{self.subscription_id}] ---[UNSUBSCRIBE] --->[{target.upper()}] (ID: {external_sub_id})"
        )

        nf_uri = nrf.get_nf_uri(target)
        if not nf_uri:
            logger.warning(
                f"[{self.subscription_id}] NF URI를 찾을 수 없음: {target}. 구독 해지 취소."
            )
            return

        unsubscription_url = f"{nf_uri}/subscriptions/{external_sub_id}"
        logger.info(f"[{self.subscription_id}] Sending DELETE to: {unsubscription_url}")

        try:
            response = await self._client.delete(unsubscription_url)
            if response.status_code in (204, 200):
                logger.info(
                    f"[{self.subscription_id}] {target.upper()} 구독 해지 성공. ID: {external_sub_id}"
                )
            else:
                logger.warning(
                    f"[{self.subscription_id}] {target.upper()} 구독 해지 실패 (Status: {response.status_code})."
                )
        except Exception as e:
            logger.error(
                f"[{self.subscription_id}] {target.upper()} 구독 해지 중 오류 발생: {e}"
            )

        # UI 업데이트를 위해 관계 제거 통보 (관계 관리자를 통해 WebSocket 메시지 전송)
        if self._relation_manager is not None:
            try:
                await self._relation_manager.remove_relations_by_sub_id(external_sub_id)
            except Exception as e:
                logger.error(f"Failed to remove relation: {e}")

    async def _notify_analyzing(self, subscription_id: str):
        """
        데이터 분석 시작 및 종료 알림
        : 실제로 제어명령 생성을 위해서 신경망 통과 시작부터 종료시까지의 시점을 UI에게 알리는 용도
        """
        await broadcast_web_message(
            sub_id=subscription_id,
            from_node="ncof",
            to_node="ncof",
            msg_type="ANALIZING",
            data="{}",
        )

        await asyncio.sleep(3)  #

        await broadcast_web_message(
            sub_id=subscription_id,
            from_node="ncof",
            to_node="ncof",
            msg_type="ANALIZED",
            data="{}",
        )

    async def _periodic_process(self):
        """
        주기적으로 데이터를 분석하고 결과를 통보한다.
        """

        if self.subscription.evt_req is None:
            return

        period = (
            self.subscription.evt_req.rep_period
            if self.subscription.evt_req.rep_period is not None
            else 60
        )
        try:
            while self.is_running:
                logger.info(f"[{self.subscription_id}] 주기적 분석 시작")

                # 시각적 효과
                asyncio.create_task(self._notify_analyzing(self.subscription_id))

                await asyncio.sleep(period)
                nf_type = self._get_source_nf_type()
                if nf_type is None:
                    logger.warning(f"cannot retrieve control type...")
                    continue

                await self._analyze_data(nf_type)
                # if analysis_results:
                # await self.notify_subscriber(nf_type, analysis_results)
        except asyncio.CancelledError as e:
            print(e)
            pass

    def _get_qos_template(self) -> Optional[List[Dict[str, Any]]]:
        qos_template_file = (
            "14_e_NncofEventsSubscriptionNotification_from NCOF_to_PCF_v1.0.json"
        )
        qos_template_file_path = Path(__file__).parent / qos_template_file

        try:
            with open(qos_template_file_path, "r", encoding="utf-8") as f:
                qos_template = json.load(f)
            return qos_template

        except FileNotFoundError:
            logger.error(f"템플릿 파일을 찾을 수 없습니다: {qos_template_file_path}")
            # 상황에 따라 예외를 다시 던지거나(raise), None을 반환하도록 처리합니다.
            return None
        except json.JSONDecodeError as e:
            logger.error(
                f"JSON 파일 파싱에 실패했습니다. 형식을 확인해주세요. 오류: {e}"
            )
            return None

    def _get_upf_wlan_performance(self) -> NotificationData | None:
        """
        Notifications 목록중에  UPF로 부터 수신 한 12p_c 인 것을 반환한다.
        """
        notifications = self.notif_data_store.get_all()
        for key, notif in notifications.items():
            if isinstance(notif, NotificationData):
                if len(notif.notification_items) == 1:
                    # notificatio_items 의 개수가 0 인 것을 찾는다.
                    return notif
        return None

    async def _analyze_data(
        self, nf_type: str
    ) -> NncofEventsSubscriptionNotification | None:
        """
        수집된 원시 데이터를 분석하여 제어용 Notification 을 생성한다.
        편의를 위해서 JSON 템플릿 파일을 읽어 NncofEventsSubscriptionNotification 을 생성한다.
        """
        notifications = self.notif_data_store.get_all()
        logger.info(f"[{self.subscription_id}] 데이터 분석 시작")
        # qos_template_file = (
        #     "14_e_NncofEventsSubscriptionNotification_from NCOF_to_PCF_v1.0.json"
        # )
        # qos_template_file_path = Path(__file__).parent / qos_template_file

        qos_template = self._get_qos_template()

        if qos_template is None:
            return None

        cell_notif, qos_notif = None, None

        # with open(qos_template_file_path, encoding="utf-8") as f:
        #     qos_template = json.load(f)

        notif = self._get_upf_wlan_performance()
        if notif is None:
            return None

        print(f"-----[ Received Notification from {nf_type}]-----")
        rprint(notif)
        print("======[ Generated Notfication ]=====")
        try:
            result = self.rule_engine.generate_notification(
                notif.to_dict(),
                qos_template,
                _now_iso_kst(),
                self.subscription_id,
                self.subscription.notif_corr_id,
            )

            if result is not None:
                cell_notif = result["cell_power_15f"]
                qos_notif = result["qos_policy_14e"]
                if cell_notif is not None and nf_type == "RICF":
                    rprint(cell_notif)
                    self.control_data_store.add_data(
                        nf_type.lower(), self.subscription.notif_corr_id, cell_notif[0]
                    )
                    await self._notify_subscriber("ricf", cell_notif)
                if qos_notif is not None and nf_type == "PCF":
                    rprint(qos_notif)
                    self.control_data_store.add_data(
                        nf_type.lower(),
                        f"{self.subscription.notif_corr_id}_qos",
                        qos_notif[0],
                    )
                    await self._notify_subscriber(nf_type.lower(), qos_notif)

        except Exception as e:
            print(e)
            # break

        # ncof_control_event = NncofEventsSubscriptionNotification.from_dict(
        #     cell_notif[0]
        # )
        # ncof_control_event.notif_corr_id = self.subscription.notif_corr_id

        # if ncof_control_event.notif_corr_id is not None:
        #     self.control_data_store.add_data(
        #         nf_type, ncof_control_event.notif_corr_id, ncof_control_event
        #     )
        # return ncof_control_event
        return None

    async def _notify_subscriber(
        # self, nf_type: str, ncof_control_event: NncofEventsSubscriptionNotification
        self,
        nf_type: str,
        ncof_control_event: List[Dict],
    ):
        """
        제어 명령을 NF로 전송한다.
        대상: PCF 또는 RICF
        """
        if not self.subscription.notification_uri:
            logger.warning("notification_uri is missed")
            return

        try:
            # client = httpx.AsyncClient(timeout=httpx.Timeout(5.0))
            response = await self._client.post(
                self.subscription.notification_uri, json=ncof_control_event
            )
            if response.status_code in (204, 200):
                logger.info(
                    f"[{self.subscription_id}] [{nf_type.upper()}]에게 제어명령 전송 완료"
                )
            else:
                logger.warning(
                    f"[{self.subscription_id}] 제어명령 실패\n"
                    f"  status_code : {response.status_code}\n"
                    f"  url         : {response.url}\n"
                    f"  reason      : {response.reason_phrase}\n"
                    f"  response    : {response.text}"
                )
            if self._relation_manager is not None:
                await self._relation_manager.add_relation(
                    from_node="ncof",
                    to_node=nf_type.lower(),
                    msg_type="NOTIFICATION",
                    data=jsonable_encoder(ncof_control_event),
                    sub_id=self.subscription_id,
                )

        except httpx.HTTPStatusError as e:
            # ✅ raise_for_status() 사용 시 4xx, 5xx 오류
            logger.error(
                f"[{self.subscription_id}] HTTP 상태 오류\n"
                f"  status_code : {e.response.status_code}\n"
                f"  url         : {e.request.url}\n"
                f"  response    : {e.response.text}"
            )

        except Exception as e:
            logger.error(f"[{self.subscription_id}] 제어명령 전송 중 오류 발생: {e}")

        logger.info(
            f"[{self.subscription_id}] {self.subscription.notification_uri}로 분석 결과 전송"
        )

    async def start(self):
        """
        구독에 대한 핸들러를 시작한다.
        1. 데이터 수집을 위한 하위 구독 요청 보내기
        2. 비동기 태스크 시작 (주기적 분석)
        """
        self.is_running = True
        logger.info(f"[{self.subscription_id}] 시작됨. 외부 NF 구독 절차 실행.")

        subscription_requests = build_subscription_requests(
            self.subscription_id, self.subscription
        )
        for sub_req in subscription_requests:

            target = sub_req.get("target")
            subscription = sub_req.get("subscription")

            # 외부 NF로 구독 요청을 보내고 생성된 구독 ID를 받아옴
            external_sub_id = await self._send_external_subscription(
                target, subscription
            )

            if external_sub_id:
                self.external_subscriptions.append(
                    {
                        "target": target,
                        "external_sub_id": external_sub_id,
                        "subscription": subscription,
                    }
                )
                logger.info(
                    f"[{self.subscription_id}] [{target.upper()}] 구독 성공. ID: {external_sub_id}"
                )
                # 관계 관리자를 통해 관계 기록 (NCOF -> 외부 NF)
                if self._relation_manager is not None:
                    try:
                        await self._relation_manager.add_relation(
                            from_node="ncof",
                            to_node=target.lower(),
                            msg_type="SUBSCRIBED",
                            data=jsonable_encoder(subscription),
                            sub_id=external_sub_id,
                        )
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.error(f"Failed to add relation: {e}")

        if self.subscription.evt_req and self.subscription.evt_req.rep_period:
            self._task = asyncio.create_task(self._periodic_process())

    async def stop(self):
        """
        구독 핸들러 정지. 주기적 분석 태스크를 중단하고 외부 NF들에게 구독 해지 요청을 보낸다.
        """
        self.is_running = False

        # 1. 분석 태스크 중단
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # 2. 외부 NF 구독 해지 (Unsubscribe)
        logger.info(f"[{self.subscription_id}] 외부 NF 구독 해지 절차 시작")
        for sub_info in self.external_subscriptions:
            target = sub_info["target"]
            ext_id = sub_info["external_sub_id"]
            if ext_id:
                await self._send_external_unsubscription(target, ext_id)

        self.external_subscriptions.clear()
        # HTTP 클라이언트 정리
        await self._client.aclose()
        logger.info(f"[{self.subscription_id}] 정지됨.")

    def handle_notification(
        self, source_nf: str, notif_data: NotificationData | NefEventExposureNotif
    ):
        """
        NF로부터 수신한 Notification 데이터를 notif_id 또는 correlation_id 별로 DataStore에 저장한다.
        """
        notif_id = None
        if isinstance(notif_data, NotificationData):
            notif_id = notif_data.correlation_id
        elif isinstance(notif_data, NefEventExposureNotif):
            notif_id = notif_data.notif_id

        if notif_id is None:
            logger.warning(
                "cannot retrieve notif_id - checkout correlation_id or notif_id field"
            )
            return

        self.notif_data_store.add_data(source_nf, notif_id, notif_data)
        logger.debug(
            f"[{self.subscription_id}] [{source_nf}]로부터 데이터 notif_id: [{notif_id}]수신 및 분류 저장 완료."
        )

    def get_external_subscriptions(self) -> List[ExternalSubscriptionRequest]:
        """
        핸들러가 외부 NF로 보낸 구독요청 목록을 반환한다.
        """
        return list(self.external_subscriptions)
