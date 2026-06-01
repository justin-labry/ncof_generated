# AGENTS.md — src/nncof/apis/

## OVERVIEW

API 라우터 계층. OpenAPI Generator가 생성한 base 라우터 + 수동 구현 라우터로 구성된다. NCOF Events Subscription REST API와 Web UI 대시보드용 Web API, NF(UPF/NEF) 알림 수신 라우터 포함.

## STRUCTURE

```
apis/
├── *_api_base.py           # OpenAPI 생성. 수정 금지. (6개 파일)
├── *_api.py                # 수동 구현. *_api_base를 상속/대체. (6개 파일)
├── web_api.py              # Web UI 대시보드용 REST API (수동)
├── nef_events_notifications_*.py   # NEF 알림 수신
├── upf_events_notifications_*.py   # UPF 알림 수신
└── __init__.py             # 빈 파일
```

## WHERE TO LOOK

| 라우터 | 엔드포인트 | 목적 |
|--------|-----------|------|
| `individual_ncof_events_subscription_document_api.py` | `GET/PUT/PATCH/DELETE /subscriptions/{id}` | 개별 구독 조회/수정/삭제 |
| `ncof_events_subscriptions_collection_api.py` | `GET/POST /subscriptions` | 구독 목록 조회/생성 |
| `ncof_event_subscription_transfers_collection_api.py` | `POST /transfers` | 구독 전송 |
| `individual_ncof_event_subscription_transfer_document_api.py` | `GET /transfers/{id}` | 전송 상태 조회 |
| `nef_events_notifications_api.py` | `POST /notifications/nef` | NEF 이벤트 알림 수신 |
| `upf_events_notifications_api.py` | `POST /notifications/upf` | UPF 이벤트 알림 수신 |
| `web_api.py` | `GET /api/subscriptions`, `GET /api/logs`, `WS /ws` | Web UI 대시보드 |

## CONVENTIONS

- **OpenAPI base + custom impl** — `*_api_base.py`는 OpenAPI Generator 산출물. 직접 수정 금지. `*_api.py`가 base를 import하여 router 등록.
- **Impl 레이어 호출** — 라우터는 `nncof.impl.*` 또는 `nncof.core.*`의 함수를 호출만 함. 비즈니스 로직 없음.
- **WebSocket** — `web_api.py`의 `/ws` 엔드포인트로 브라우저 대시보드와 실시간 통신.

## ANTI-PATTERNS

- **__init__.py 빈 파일** — import 경로 설정 외 역할 없음. 패키지 문서화 부재.
- **Base 파일 중복** — 각 API마다 _base.py와 _api.py가 1:1로 존재. 구조를 이해하지 못하면 혼동 유발.
