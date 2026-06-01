# AGENTS.md

**Generated:** 2026-05-13
**Branch:** master

## OVERVIEW

NCOF Event Exposure Service — 6G-I2P PoC용 FastAPI 서버. NncofEventsSubscription OpenAPI 스펙에서 생성되었으며, 다중 NF(nsmf/nnef/upf)로부터 이벤트 구독을 관리한다. uv workspace monorepo(nsmf-server, nupf-server, nnef-server)의 일원.

## STRUCTURE

```
nncof-server/
├── src/nncof/
│   ├── core/           # 비즈니스 로직: 구독 관리, 핸들러, WebSocket, NRF 연동
│   ├── apis/           # OpenAPI 생성 라우터 + 수동 라우터 (frontend Web UI)
│   ├── impl/           # API 콜백 구현체 (core 호출만)
│   └── models/         # Pydantic 모델 (OpenAPI 자동 생성, ~130개 파일)
├── tests/              # pytest + TestClient
└── README.md / pyproject.toml / CLAUDE.md
```

## WHERE TO LOOK

| Task | Path | Note |
|------|------|------|
| 구독 비즈니스 로직 | `src/nncof/core/subscription_manager.py` | Singleton. 모든 CRUD + 정규화 |
| 이벤트 처리/전파 | `src/nncof/core/subscription_handler.py` | NF별 구독 요청 생성, 데이터 수집 |
| WebSocket 실시간 통신 | `src/nncof/core/websocket_manager.py` | 브라우저 대시보드용 |
| NF 서비스 탐색 | `src/nncof/core/nrf.py` | NRF 클라이언트 (singleton) |
| IP/SUPI 매핑 | `src/nncof/core/supi_mapping.py` | JSON 기반 정적 매핑 |
| API 엔드포인트 | `src/nncof/apis/` | OpenAPI 생성본 + web_api.py |
| API 콜백 구현 | `src/nncof/impl/` | core 호출만, thin |
| 모델 정의 | `src/nncof/models/` | 전부 자동 생성, 직접 수정 금지 |
| 보안 | `src/nncof/security_api.py` | OAuth2 client credentials (stub) |
| 진입점 | `src/nncof/main.py` | FastAPI app + router 등록 |
| E2E 테스트 | `tests/` | pytest + TestClient |

## CONVENTIONS

- **uv workspace** — nncof-server는 nsmf-server, nnef-server에 의존 (`tool.uv.sources`로 path 참조)
- **OpenAPI base + custom impl 패턴** — `*_api_base.py`(생성본, 미수정) + `*_api.py`(수동, 생성본 상속하여 구현)
- **Singleton 패턴** — SubscriptionManager, ConnectionManager, nrf는 모듈 레벨 인스턴스
- **한글 주석** — 비즈니스 로직 주석은 한국어
- **Python >= 3.12** — 타입 힌트 사용
- **PYTHONPATH=src** — 실행 시 필수
- **Pydantic v2** — OpenAPI Generator 기본 출력

## ANTI-PATTERNS (THIS PROJECT)

- **임포트 순환 참조** — subscription_handler.py 내부에서 `from nncof.core.subscription_manager import`를 함수 내부에서 지연 임포트함. subscription_manager ↔ subscription_handler 순환 의존.
- **전역 가변 상태** — SubscriptionManager, nrf 인스턴스는 모듈 레벨에서 생성됨. 테스트 간 격리 주의.
- **보안 stub** — `security_api.py`의 OAuth2 검증은 빈 문자열 반환 (PoC). 운영 환경에서 반드시 교체.

## UNIQUE STYLES

- **subscription_request_builder.py** — 단일 파일에 모든 NF별 구독 요청 변환 로직 집중 (~600줄). nsmf/nnef/upf 세 가지 NF 타입을 `_handle_*` 프라이빗 함수로 분기.
- **normalize_subscription()** — NncofEventsSubscription / NsmfEventExposure / NefEventExposureSubsc 세 타입을 공통 dict로 변환. subscription_manager.py의 핵심 진입점.

## COMMANDS

```bash
# 서버 실행 (uv)
PYTHONPATH=src uvicorn nncof.main:app --host 0.0.0.0 --port 8080

# 서버 실행 (pip)
pip3 install -r requirements.txt
PYTHONPATH=src uvicorn nncof.main:app --host 0.0.0.0 --port 8080

# Docker
docker compose up --build

# 테스트
PYTHONPATH=src pytest tests

# 의존성 추가
uv add <package>
```

## SEE ALSO

- `src/nncof/core/AGENTS.md` — 비즈니스 로직 계층 상세
- `src/nncof/apis/AGENTS.md` — API 라우터 계층 상세

## NOTES

- `models/` 디렉토리는 OpenAPI Generator로 재생성 가능. 수동 수정 시 재생성 시 덮어쓰기됨.
- nsmf-server와 nnef-server는 같은 monorepo 내 workspace 멤버. `pip install -e ../nsmf-server` 또는 uv source 참조 필요.
- 정적 파일은 `src/nncof/static/`에서 서빙. Web UI 대시보드용 index.html.
