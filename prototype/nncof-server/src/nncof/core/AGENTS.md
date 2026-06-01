# AGENTS.md — src/nncof/core/

## OVERVIEW

비즈니스 로직 계층. 구독 CRUD, NF별 이벤트 구독 요청 생성, WebSocket 실시간 브로드캐스트, NRF 연동, SUPI/IP 매핑을 담당.

## STRUCTURE

```
core/
├── subscription_manager.py     # 구독 CRUD + 정규화 (Singleton, 383줄)
├── subscription_handler.py     # NF별 구독 요청 생성/전송 + 데이터 수집 (393줄)
├── subscription_request_builder.py  # nsmf/nnef/upf 요청 변환 (600줄)
├── websocket_manager.py        # WebSocket 연결 관리 + 브로드캐스트
├── nrf.py                      # NRF (NF Repository Function) 클라이언트
├── supi_mapping.py             # SUPI <-> IP 정적 매핑 (JSON)
├── utils.py                    # safe_get, safe_set, print_logo, timestamp
├── logging_config.yaml         # 로깅 설정
└── __init__.py                 # 빈 파일
```

## WHERE TO LOOK

| 파일 | 역할 |
|------|------|
| `subscription_manager.py` | 구독 생성/조회/삭제, normalize_subscription(), 순환 참조 지연 임포트 |
| `subscription_handler.py` | SubscriptionDataStore, NF로 구독 요청 전송, 이벤트 데이터 수집 |
| `subscription_request_builder.py` | NF 타입별 구독 요청 구성 (`_handle_*` 프라이빗 함수 7개) |
| `websocket_manager.py` | ConnectionManager (Singleton), broadcast_web_message |
| `nrf.py` | NFDiscovery 클래스, NRF로 서비스 조회 |

## CONVENTIONS

- **Singleton by module-level instance** — `manager = ConnectionManager()`, `nrf = NFDiscovery()` 등은 모듈 로드 시 생성
- **내부 지연 임포트** — 순환 참조 회피를 위해 함수 내부에서 `from nncof.core.subscription_manager import SubscriptionManager` 실행
- **jsonable_encoder** — FastAPI의 jsonable_encoder()로 모델 직렬화 후 HTTP 전송
- **한글 독스트링** — 비즈니스 로직 설명은 한국어

## ANTI-PATTERNS

- **순환 참조** — subscription_manager → subscription_handler ↔ subscription_manager. 지연 임포트로 회피 중.
- **단일 파일 과책임** — subscription_request_builder.py는 600줄로 7개 NF 타입 처리 모두 포함. 분리 고려.
- **전역 상태** — ConnectionManager, SubscriptionManager 인스턴스는 프로세스 수명 동안 유지. 테스트 시 격리 어려움.
