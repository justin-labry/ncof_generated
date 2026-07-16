# NCOF 구독 요청 REST API 클라이언트
# JSON 파일을 읽어 POST 요청을 전송한다.

import json
import sys
from pathlib import Path
from typing import Any

import logging
import os
from typing import Any

from dotenv import dotenv_values

import httpx
from rich.pretty import pprint

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NCOF_Client")


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


NCOF_PORT = _cfg("NCOF_PORT", "9000")
HOST = _cfg("NF_HOST", "127.0.0.1")

logger.info(f"NCOF_PORT: {NCOF_PORT}")

BASE_URL = f"https://{HOST}:{NCOF_PORT}"
ENDPOINT = "/subscriptions"

TLS_VERIFY: bool | str = False

MENU = [
    ("1", "[SUBSCRIPTION] PCF -> NCOF", "subscription_pcf_to_ncof.json"),
    ("2", "[SUBSCRIPTION] RICF -> NCOF", "subscription_ricf_to_ncof.json"),
]


def print_menu() -> None:
    print("\n=== NCOF Subscription Client ===")
    print(f"POST {BASE_URL}{ENDPOINT}\n")

    for key, label, _ in MENU:
        print(f"  [{key}] {label}")

    print("  [q] 종료")
    print()


def load_json(filepath: str) -> Any:
    path = Path(filepath)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def send_request(
    client: httpx.Client,
    payload: Any,
) -> None:
    try:
        response = client.post(
            ENDPOINT,
            json=payload,
        )

        print(
            f"\n[응답] HTTP {response.status_code} "
            f"{response.reason_phrase} ({response.http_version})"
        )

        try:
            pprint(response.json(), max_depth=3)
        except json.JSONDecodeError:
            print(response.text)

        response.raise_for_status()

    except httpx.HTTPStatusError:
        # 응답 본문은 위에서 이미 출력했으므로 추가 출력하지 않는다.
        pass

    except httpx.ConnectError as error:
        print(f"\n[오류] 서버 연결 실패: {error}")

    except httpx.TimeoutException as error:
        print(f"\n[오류] 요청 시간 초과: {error}")

    except httpx.TransportError as error:
        print(f"\n[오류] 통신 실패: {error}")


def main() -> None:
    timeout = httpx.Timeout(
        connect=5.0,
        read=30.0,
        write=30.0,
        pool=5.0,
    )

    try:
        with httpx.Client(
            base_url=BASE_URL,
            http2=True,
            verify=TLS_VERIFY,
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        ) as client:
            while True:
                print_menu()
                choice = input("선택 > ").strip()

                if choice.lower() == "q":
                    print("종료합니다.")
                    return

                matched = next(
                    (
                        (label, filename)
                        for key, label, filename in MENU
                        if choice == key
                    ),
                    None,
                )

                if matched is None:
                    print(f"올바른 번호를 선택하세요 (1-{len(MENU)})")
                    continue

                label, filename = matched
                print(f"\n→ {label} 요청 전송 중 ...")

                try:
                    payload = load_json(filename)
                except FileNotFoundError:
                    print(f"[오류] 파일을 찾을 수 없음: {filename}")
                    continue
                except json.JSONDecodeError as error:
                    print(
                        f"[오류] JSON 파싱 실패: "
                        f"{filename}:{error.lineno}:{error.colno} "
                        f"{error.msg}"
                    )
                    continue
                except OSError as error:
                    print(f"[오류] 파일 읽기 실패: {error}")
                    continue

                send_request(client, payload)

    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
