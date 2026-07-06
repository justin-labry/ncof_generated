# nsmf-server AGENTS.md

**Generated:** 2026-05-13

## OVERVIEW

SMF SBI Mockup — Nsmf_EventExposure 서비스 (3GPP TS 29.508). 6G-I2P PoC에서 SMF 역할을 흉내내는 FastAPI 서버. uv workspace monorepo의 일원.

## STRUCTURE

```
nsmf-server/
├── src/nsmf/
│   ├── main.py                        # 진입점 (2개 router 등록)
│   ├── security_api.py                # OAuth2 stub (PoC)
│   ├── apis/
│   │   ├── subscriptions_collection_api.py           # POST /subscriptions
│   │   ├── subscriptions_collection_api_base.py       # 생성본 (수정 금지)
│   │   ├── individual_subscription_document_api.py    # GET/PUT/DELETE /subscriptions/{subId}
│   │   └── individual_subscription_document_api_base.py  # 생성본 (수정 금지)
│   ├── impl/
│   │   ├── subscriptions_collection_api_impl.py  # 유일한 실제 구현
│   │   ├── utils.py                              # load_json, notify (httpx), print_logo
│   │   ├── simulation.py                         # QoS/USER_DATA 시뮬레이션
│   │   └── *_v1.0.json                           # 3개 mock 데이터 파일
│   └── models/          # 65개 Pydantic 모델 (OpenAPI 자동 생성, 수정 금지)
├── tests/
│   ├── conftest.py      # TestClient fixture
│   └── test_*.py        # 생성된 stub — 전부 주석 처리됨 (실행 불가)
└── openapi.yaml         # 원본 OpenAPI 스펙
```

## API ENDPOINTS

| Method | Path | Impl 상태 | 설명 |
|--------|------|-----------|------|
| POST | `/subscriptions` | ✅ 구현됨 | 구독 생성 + 주기적 notification 전송 시작 |
| GET | `/subscriptions/{subId}` | ❌ 미구현 → 500 | 개별 구독 조회 |
| PUT | `/subscriptions/{subId}` | ❌ 미구현 → 500 | 구독 갱신 |
| DELETE | `/subscriptions/{subId}` | ❌ 미구현 → 500 | 구독 삭제 |

**중요:** GET/PUT/DELETE는 impl 클래스가 없어서 500을 반환한다. POST만 동작한다.

## KEY ARCHITECTURE

**Plugin 클래스 발견 패턴:**
- `*_api.py`가 `pkgutil.iter_modules`로 `nsmf.impl` 패키지를 스캔
- `Base*Api.__init_subclass__`로 하위클래스 자동 등록
- `Base*Api.subclasses[0]()`로 호출. 즉 impl 클래스가 없으면 500.

**구독 생성 (POST) 동작 흐름:**
1. 요청 body의 `event_subs[0].upf_events` 길이로 mock JSON 파일 선택
2. NotificationData 생성 → `_subscriptions[sub_id]`에 저장
3. `asyncio.create_task(_periodic_notification_sender)` — rep_period(기본 10초) 간격
4. POST는 subscription-id를 응답 헤더로 반환
5. 주기적 전송: expiry 시간에 도달하면 중단, notif_uri로 httpx POST

**시뮬레이션 (`simulation.py`):**
- NotificationData를 받아서 각 NotificationItem의 필드를 랜덤 변화
- `QOS_MONITORING`: packet_delay, jitter, throughput, congestion 등 변동
- `USER_DATA_USAGE_MEASURES`: volume 증가, throughput 변동
- 실제 데이터가 실시간으로 변하는 효과를 냄

## DEPENDENCIES

- **nupf-server** — `nupf.models.notification_data.NotificationData`를 import함
- httpx — NF로 notification 전송용
- run.sh: `PORT=8001` 기본값, uv + uvicorn --reload

## GOTCHAS

- **테스트 전부 주석 처리** — 생성된 stub이며, import 경로가 `openapi_server`로 잘못되어 있다. 실행하려면 import 수정 + 주석 해제 필요.
- **Dockerfile이 python:3.7 사용** — 프로젝트 요구사항(Python>=3.12)과 불일치.
- **보안 stub** — `security_api.py`의 `oauth2_()`는 빈 문자열 반환. 모든 Security 의존성을 통과하지만 실제 검증은 안 함.
- **전역 상태** — `_subscriptions` 딕셔너리는 프로세스 메모리에 저장. 재시작 시 소멸.
- **mock JSON 파일 선택 기준** — `upf_events` 배열 길이: 5→`8_*.json`, 3→`8p_*.json`, 그 외→`12_c_*.json`.
- **uv workspace member** — `nsmf-server`는 `nupf-server`에 workspace 의존. `uv sync`를 루트에서 먼저 실행해야 함.

## COMMANDS

```bash
cd nsmf-server && sh run.sh                          # 실행 (port 8001)
PORT=9999 sh run.sh                                   # 포트 오버라이드
cd .. && uv sync                                      # 워크스페이스 의존성 설치 (루트에서)
cd nsmf-server && PYTHONPATH=src pytest tests/        # 테스트 (실행 가능한 테스트 없음)
```
