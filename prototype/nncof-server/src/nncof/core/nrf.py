import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NF_Discovery")


class NFDiscovery:
    def __init__(self, use_nrf=False):
        self.use_nrf = use_nrf
        # Dummy 데이터베이스: NRF 연동 전까지 사용할 로컬 맵핑
        self._dummy_nfs = {
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
