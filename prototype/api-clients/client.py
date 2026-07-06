# NCOF 구독 요청 REST API 클라이언트
# .http 파일의 패턴을 따라 JSON 파일을 읽어 POST 요청을 보낸다

import json
import sys
import urllib.request
import urllib.error

from rich.pretty import pprint

BASE_URL = "http://localhost:8000"
ENDPOINT = "/subscriptions"
HEADERS = {"Content-Type": "application/json"}

MENU = [
    ("1", "[SUBSCRIPTION] PCF -> NCOF", "subscription_pcf_to_ncof.json"),
    ("2", "[SUBSCRIPTION] RICF -> NCOF", "subscription_ricf_to_ncof.json"),
]


def print_menu():
    print("\n=== NCOF Subscription Client ===")
    print(f"POST {BASE_URL}{ENDPOINT}\n")
    for key, label, _ in MENU:
        print(f"  [{key}] {label}")
    print(f"  [q] 종료")
    print()


def load_json(filepath: str) -> bytes:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().encode("utf-8")


def send_request(payload: bytes):
    req = urllib.request.Request(
        f"{BASE_URL}{ENDPOINT}",
        data=payload,
        headers=HEADERS,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            print(f"\n[응답] HTTP {resp.status} {resp.reason}")
            try:
                parsed = json.loads(body)
                # print(json.dumps(parsed, indent=2, ensure_ascii=False))
                pprint(parsed, max_depth=3)
            except json.JSONDecodeError:
                print(body)
    except urllib.error.HTTPError as e:
        print(f"\n[오류] HTTP {e.code} {e.reason}")
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
            # pprint(json.dumps(parsed, indent=2, ensure_ascii=False))
            pprint(parsed, max_depth=3)
        except json.JSONDecodeError:
            pprint(body)
    except urllib.error.URLError as e:
        print(f"\n[오류] 서버 연결 실패: {e.reason}")


def main():
    while True:
        print_menu()
        choice = input("선택 > ").strip()

        if choice.lower() == "q":
            print("종료합니다.")
            sys.exit(0)

        matched = None
        for key, label, filename in MENU:
            if choice == key:
                matched = (label, filename)
                break

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
        except json.JSONDecodeError as e:
            print(f"[오류] JSON 파싱 실패: {e}")
            continue

        send_request(payload)


if __name__ == "__main__":
    main()
