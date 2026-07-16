import logging
import os
from typing import Any

from dotenv import dotenv_values

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NF_Discovery")


def _find_upwards(filename: str) -> str | None:
    """__file__ 기준 상위 디렉토리로 올라가며 filename 을 찾는다."""
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        candidate = os.path.join(current, filename)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


# 포트 단일 출처(prototype/nf_ports.conf)를 읽어온다.
_ports_file = _find_upwards("nf_ports.conf")
_conf: dict[str, str | None] = dict(dotenv_values(_ports_file)) if _ports_file else {}
if _ports_file:
    logger.info(f"[NRF] NF ports loaded from {_ports_file}")
else:
    logger.warning("[NRF] nf_ports.conf not found; using built-in default ports.")


def _cfg(key: str, default: str) -> str:
    """조회 우선순위: OS 환경변수 > nf_ports.conf > 기본값."""
    return os.getenv(key) or _conf.get(key) or default


def _build_dummy_nfs() -> dict[str, Any]:
    """nf_ports.conf 의 host/port 로 NF 조회 테이블을 조립한다.

    서비스 경로(/nnef-eventexposure/af/v1 등)는 구조적이고 거의 바뀌지 않으므로
    코드에 유지하고, 자주 바뀌는 host/port 만 nf_ports.conf 로 외부화한다.
    """
    host = _cfg("NF_HOST", "127.0.0.1")
    smf_port = _cfg("SMF_PORT", "9001")
    nef_port = _cfg("NEF_PORT", "9002")  # AF/RICF 는 NEF 서버가 경로로 구분해 함께 처리
    pcf_port = _cfg("PCF_PORT", "9004")
    return {
        "SMF": {
            "base_uri": f"https://{host}:{smf_port}",
            "services": {"nsmf-eventexposure": "/nsmf-eventexposure/v1"},
        },
        "AF": {
            "base_uri": f"https://{host}:{nef_port}/nnef-eventexposure/af/v1",
            "services": {"naf-eventexposure": "/naf-eventexposure/v1"},
        },
        "RICF": {
            "base_uri": f"https://{host}:{nef_port}/nnef-eventexposure/ricf/v1",
            "services": {"nsmf-eventexposure": "/nsmf-eventexposure/v1"},
        },
        "PCF": {
            "base_uri": f"https://{host}:{pcf_port}",
            "services": {"npcf-eventexposure": "/npcf-eventexposure/v1"},
        },
    }


# 모듈 로드 시 NF 조회 테이블을 조립한다.
_dummy_nfs: dict[str, Any] = _build_dummy_nfs()


class NFDiscovery:
    """
    NF 조회를 위한 클래스
    """

    def __init__(self, use_nrf=False):
        self.use_nrf = use_nrf
        self._dummy_nfs = _dummy_nfs

    def get_nf_uri(self, nf_type: str, service_name: str = "") -> str:
        """
        NF 타입과 서비스 이름을 기반으로 SBI URI를 획득합니다.
        """
        if self.use_nrf:
            # --- TODO: 실제 NRF Nnrf_NFDiscovery API 호출 로직 구현 ---
            # response = requests.get(f"{NRF_URL}/nnrf-disc/v1/nf-instances?target-nf-type={nf_type}")
            # return self._parse_nrf_response(response, service_name)
            logger.info(f"[NRF] {nf_type} discovery requested (Not Implemented)")
            return "http://nrf-discovery-not-implemented.local"

        # Dummy 로직
        nf_info = self._dummy_nfs.get(nf_type.upper())
        if not nf_info:
            logger.error(f"NF Type '{nf_type}' not found in dummy database.")
            return ""

        base = nf_info["base_uri"]

        # 특정 서비스 경로가 요청된 경우
        if service_name:
            service_path = nf_info["services"].get(service_name.lower(), "")
            if not service_path:
                logger.warning(
                    f"Service '{service_name}' not defined for {nf_type}. Returning base URI."
                )
            return f"{base}{service_path}"

        return base


nrf = NFDiscovery(use_nrf=False)  # 현재는 Dummy 모드

if __name__ == "__main__":
    # --- 사용 예시 ---
    discovery = NFDiscovery(use_nrf=False)  # 현재는 Dummy 모드

    smf_base = discovery.get_nf_uri("SMF")
    print(f"SMF Base URI: {smf_base}")
