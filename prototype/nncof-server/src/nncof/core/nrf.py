import json
import logging
import os
from typing import Any

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NF_Discovery")

def _find_project_root(marker: str = "pyproject.toml") -> str:
    """pyproject.toml이 있는 디렉토리를 프로젝트 루트로 간주하고 상위로 탐색한다."""
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(current, marker)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError(f"Cannot find project root ({marker})")
        current = parent


# 프로젝트 루트 기준 JSON 설정 파일 경로
_config_file_path = os.path.join(_find_project_root(), "nrf_dummy_nfs.json")


def _load_dummy_nfs() -> dict[str, Any]:
    """nrf_dummy_nfs.json 파일에서 Dummy NF 설정을 읽어온다. 파일이 없으면 하드코딩된 기본값을 반환한다."""
    _default_nfs = {
        "SMF": {
            "base_uri": "http://127.0.0.1:8001",
            "services": {"nsmf-eventexposure": "/nsmf-eventexposure/v1"},
        },
        "AF": {
            "base_uri": "http://127.0.0.1:8002",
            "services": {"naf-eventexposure": "/naf-eventexposure/v1"},
        },
        "RICF": {
            "base_uri": "http://127.0.0.1:8003",
            "services": {
                "nsmf-eventexposure": "/nsmf-eventexposure/v1",
            },
        },
        "PCF": {
            "base_uri": "http://127.0.0.1:8004",
            "services": {
                "npcf-eventexposure": "/npcf-eventexposure/v1",
            },
        },
    }
    try:
        with open(_config_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(
                f"[NRF] Dummy NF config loaded from {_config_file_path}"
            )
            return data
    except FileNotFoundError:
        logger.warning(
            f"[NRF] Config file not found at {_config_file_path}. Using hardcoded defaults."
        )
        return _default_nfs
    except json.JSONDecodeError as e:
        logger.error(
            f"[NRF] Invalid JSON in config file: {e}. Using hardcoded defaults."
        )
        return _default_nfs


# 모듈 로드 시 Dummy NF 설정을 JSON 파일에서 읽어온다
_dummy_nfs: dict[str, Any] = _load_dummy_nfs()


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
