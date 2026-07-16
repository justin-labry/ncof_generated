# NCOF 

## 저장소 내 위치

이 디렉터리(`prototype/`)는 `ncof_generated` 저장소의 **동작하는 PoC 구현**이다. 병합(modutech → main) 이후 저장소는 세 영역으로 구성된다.

| 디렉터리 | 내용 |
|---|---|
| `prototype/` | **이 문서** — uv 워크스페이스 기반 서버들 + Vue UI (실제 실행/시연) |
| `generated/` | OpenAPI Generator 가 만든 FastAPI 스텁 원본 + `test_server.py`(단일 포트 통합 실행). 자체 `README.md` 보유 |
| `gym_for_ncof/` | gNB#2 sleep/active 결정용 RL 환경(Gymnasium + PPO). 학습된 정책 JSON 을 NCOF 가 로드 |

아래 실행 절차의 모든 명령은 `prototype/` 디렉터리 안에서 수행한다.

## 사전설치

NCOF 프로젝트 실행을 위해서 아래 사항들을 준비한다.

- uv 설치 (0.6.12)
- python 설치 (3.12.9)
- nodejs 설치 (v24.13.1): UI 개발용

## 환경설정 (.env, 선택)

`nncof-server/` 는 `.env` 없이도 기본값으로 기동된다(`APP_TITLE` 등에 기본값이 내장됨). 알림 base URI·결정 엔진 등 기본 동작을 바꿀 때만 제공된 예시를 복사해 **선택적으로** 설정한다.

```sh
cd nncof-server
cp .env.example .env   # 선택 — 기본 동작을 바꿀 때만
```

> 최초 1회 `uv sync --all-packages`(아래) 만 해두면 `.env` 없이 그대로 실행된다.

## 의존성 설치 (uv 워크스페이스)

`prototype/` 는 5개 서버를 멤버로 갖는 uv 워크스페이스이며 하나의 공유 venv 를 사용한다. 최초 1회 전체 동기화한다.

```sh
cd prototype
uv sync --all-packages
```

> 일부 서버는 형제 패키지를 import 한다(예: nnef-server → `nncof_cb`, `nncof`). 공유 venv 에서 특정 서버만 동기화되면 형제 패키지가 제거되어 `ModuleNotFoundError` 가 날 수 있으므로, 위 `uv sync --all-packages` 로 전체를 한 번 설치해 둔다. 각 실행 스크립트는 `uv run --no-sync` 로 실행되어 venv 를 다시 건드리지 않으므로, **최초 1회 전체 동기화 후에는 추가 환경변수 없이 그대로 동작한다.**

> ⚠️ **HTTP/2 관련 재동기화 주의.** HTTP/2 서버는 `hypercorn[h2]` 로 구동된다(아래). 이 의존성은 `nncof-server/pyproject.toml` 에 이미 선언되어 있으므로 위 `uv sync --all-packages` 가 함께 설치한다. 단, **HTTP/2 변경 이전에 만들어 둔 기존 venv 를 쓰는 경우** 반드시 `uv sync --all-packages` 를 다시 실행해야 한다. (실행 스크립트가 `--no-sync` 이므로, hypercorn 미설치 상태로는 `run_http2.sh` 가 `ModuleNotFoundError: hypercorn` 로 실패한다.)

## 프로토콜: HTTP/2 (기본 h2c, TLS 토글)

NF 간 통신은 **HTTP/2** 로 운용한다. 기본은 **h2c(평문 HTTP/2, TLS 없음)** 이며, 환경변수 `NCOF_TLS` 로 **HTTP/2 over TLS** 를 켤 수 있다.

- **모드 전환**: `ncof_setting.conf` 의 `NCOF_TLS=0`(기본) → h2c(`http://`). `NCOF_TLS=1`(또는 `true`/`yes`/`on`) → TLS(`https://`). 서버·클라이언트·URL scheme·UI 프록시가 모두 이 값을 읽어 일관되게 동작한다. (CLI 환경변수가 파일값보다 우선 — 예: `NCOF_TLS=1 sh run_http2.sh`)
- **서버**: `hypercorn` 으로 단일 프로세스 기동. 기본은 평문(h2c — 연결 preface 로 HTTP/2 자동감지). `NCOF_TLS=1` 이면 `run_http2.sh` 가 `--certfile ../cert.pem --keyfile ../key.pem`(사전 생성 self-signed)을 자동으로 붙여 TLS ALPN `h2` 로 연다.
- **클라이언트**: `httpx` 사용. h2c 는 `http1=False, http2=True`(평문에서 HTTP/2 prior-knowledge 강제 — `http1` 을 켜두면 평문 연결이 조용히 HTTP/1.1 로 떨어짐), TLS 는 `http2=True, verify=False`(self-signed 허용). 각 서버 `impl/utils.py`·`core/subscription_handler.py`·`api-clients/client2.py` 의 `_httpx_kwargs()` 가 `NCOF_TLS` 로 분기한다.
- **왜 기본 h2c 인가**: 로컬/데모에서 TLS 종료 시 나오는 `SSL shutdown timed out` 잡음이 없고 설정이 단순하다. 두두원 등 TLS 연동(5G SBI 규격 TS 29.500)이 필요하면 `NCOF_TLS=1` 로 켠다. mTLS·CA 검증은 후속 단계.

> HTTP/1.1(평문) 로 띄우고 싶으면 각 서버의 기존 `run.sh` 를 사용한다. 아래 실행 절차는 **HTTP/2 기준(`run_http2.sh`)** 이다.

## 실행절차

- 4개의 터미널을 실행 후 서브프로젝트별 디렉터리로 이동하여 스크립트를 실행한다.
- 포트·TLS 등 설정은 `prototype/ncof_setting.conf` 단일 출처에서 읽는다. 바꾸려면 이 파일만 수정하고 재기동한다. (CLI 환경변수가 파일값보다 우선)

### 포트 할당 정보 (`ncof_setting.conf`)

동작에 필요한 서버는 **4개**다.

| NF (서버 디렉터리) | 포트 | 비고 |
|---|---|---|
| NCOF (`nncof-server`) | 9000 | 결정 엔진 · UI 정적 서빙 |
| SMF (`nsmf-server`) | 9001 | **SMF + UPF 목업** (`APP_MODE=SMF & UPF`) — UPF 이벤트도 이 서버가 생성·전송 |
| NEF = AF + RICF (`nnef-server`) | 9002 | 경로로 AF(`/…/af/v1`)·RICF(`/…/ricf/v1`) 구분 |
| PCF (`callback-server`) | 9004 | NCOF 제어명령 수신(PCF 목업) |

> **UPF 는 별도 서버가 아니다.** NCOF 는 UPF 이벤트를 **SMF 구독에 포함해서** 받는다(`subscription_request_builder` 가 NSMF 구독에 `upf_events` 를 첨부 → SMF 목업이 `NotificationData_from_UPF_to_NCOF` 샘플을 NCOF 의 `/notifications/upf` 로 전송). NRF 조회표에도 UPF 항목이 없어 NCOF 가 UPF 서버를 직접 호출하지 않는다. 워크스페이스의 `nupf-server`(9003)는 아무도 호출하지 않는 **독립 목업**이라 결정 루프에 띄울 필요가 없다(패키지의 Pydantic 모델만 라이브러리로 사용됨). 단독으로 띄워보려면 `cd nupf-server && sh run.sh`.

### 실행 방법 (HTTP/2)

각 서버 디렉터리로 이동해 `run_http2.sh` 를 실행한다.

기본(h2c, 평문 HTTP/2):

```sh
cd nncof-server    && sh run_http2.sh   # NCOF           → http://0.0.0.0:9000
cd nsmf-server     && sh run_http2.sh   # SMF(+UPF 목업)  → http://0.0.0.0:9001
cd nnef-server     && sh run_http2.sh   # NEF(AF+RICF)   → http://0.0.0.0:9002
cd callback-server && sh run_http2.sh   # PCF            → http://0.0.0.0:9004
```

TLS(HTTP/2 over TLS)로 띄우려면 `ncof_setting.conf` 의 `NCOF_TLS=1` 로 바꾸거나(지속), 각 명령 앞에 `NCOF_TLS=1` 을 붙인다(일시 — 파일값보다 우선). 엔드포인트가 `https://` 로 바뀐다. 서버·클라이언트·UI 를 **같은 값**으로 맞춰야 한다:

```sh
NCOF_TLS=1 sh run_http2.sh          # 일시(환경변수)
# 또는 ncof_setting.conf 에서 NCOF_TLS=1 로 지속 설정
```

- `nnef-server` 는 `run_http2.sh` 하나로 NEF 목업(AF+RICF 통합, 9002 포트)으로 실행된다. (스크립트가 `APP_MODE=NEF` 를 지정)
- 각 `run_http2.sh` 는 `hypercorn` 으로 단일 프로세스 기동한다. 기본은 평문(h2c)이고 `NCOF_TLS=1` 이면 `--certfile/--keyfile` 이 자동으로 붙는다. 기동 로그의 `Running on http://0.0.0.0:<포트>`(TLS 면 `https://`) 로 확인한다. (`--reload` 는 쓰지 않으므로 `Ctrl+C` 한 번에 종료된다.)
- 현재 구현에서 callback-server 는 PCF 가 NCOF 로부터 제어 명령을 수신하는 기능만 제공하고, 구독요청을 보내는 기능은 별도의 방법(아래 `## 확인`)을 이용한다.
- 평문 HTTP/1.1 로 띄우려면 위 명령의 `run_http2.sh` 를 `run.sh` 로 바꾼다.

## UI 실행 (nncof-ui)

대시보드(SignalViz)는 Vue 3 + Vite 기반이며 `nodejs (v24.13.1)` 환경에서 동작한다.

> nvm 으로 nodejs 를 설치한 경우, nvm 설정 추가 이전에 열어둔 터미널에서는 구버전 node 가 잡힐 수 있다. 이때는 새 터미널을 열거나 `nvm use default` 로 v24.13.1 을 활성화한다. (`node -v` 로 확인)

### 설치 및 실행

```sh
cd nncof-ui
npm install      # 최초 1회만
npm run dev      # 개발 서버 → http://localhost:5173
```

- 브라우저에서 `http://localhost:5173` 에 접속한다.
- UI 는 `/api`, `/subscriptions`, `/api/ws` 요청을 NCOF 로 프록시한다. 프록시 타깃은 `vite.config.ts` 가 `ncof_setting.conf` 의 `NCOF_PORT`/`NCOF_TLS` 를 읽어 기본 **`http://127.0.0.1:9000`**(WebSocket 은 `ws://`)로 구성한다. `ncof_setting.conf` 에서 `NCOF_TLS=1` 로 설정하거나 `NCOF_TLS=1 npm run dev` 로 실행하면 `https://`/`wss://` 로 바뀌며 self-signed 인증서를 허용하도록 `secure:false` 가 적용된다. 실시간 데이터를 확인하려면 NCOF 서버(9000)가 함께 실행 중이어야 한다.

### 원격(리모트) 접속 시 포트포워딩

리모트 서버에서 실행하는 경우 5173 포트를 로컬로 포워딩한다.

- VS Code / Cursor Remote-SSH: `PORTS` 패널에서 5173 포트를 포워딩하면 자동으로 로컬에서 접속 가능하다. (vite 는 기본 `localhost` 바인딩 그대로 사용)
- 일반 SSH: 로컬에서 `ssh -L 5173:localhost:5173 <user>@<remote-host>` 로 터널을 연 뒤 `http://localhost:5173` 접속.
- Docker 컨테이너에서 실행해 호스트의 published 포트(`-p 5173:5173`)로 접속하는 경우, vite 가 기본 `localhost` 바인딩이면 포트포워딩으로 닿지 않는다. 이때는 `npm run dev -- --host 0.0.0.0` 로 실행한다. (기동 로그에 `Network:` 줄이 보이면 외부 접속 가능 상태)

### 프로덕션 빌드

```sh
npm run build    # 타입체크(vue-tsc) → 빌드 → dist 를 nncof-server/src/nncof/static/ 로 복사
```

빌드 결과물은 NCOF 서버의 정적 파일 경로로 복사되어 기본 **`http://localhost:9000`** 에서 서빙된다. (`NCOF_TLS=1` 로 띄운 경우 `https://localhost:9000` — self-signed 이므로 브라우저에서 최초 1회 인증서 예외 허용 필요)

## 확인

PCF 또는 RICF 에서 NCOF 로 구독요청을 보내기 위해서 Postman, VS Code REST Client Plugin, Python 클라이언트 등을 사용할 수 있다.
- 방법1: VSCode 를 사용하는 경우 확장자가 `.http` 인 파일을 선택하여 요청을 보낸다. (기본 `http://…:9000`; `NCOF_TLS` 모드면 `.http` 의 `@baseUrl` 을 `https://` 로 수정)
- 방법2: 터미널에서 HTTP/2 클라이언트(`client2.py`)를 실행한다. (추천 — `NCOF_TLS` 에 맞춰 scheme·notificationURI 를 자동 정규화)

### NCOF 로 구독요청 보내기

`./api-clients/` 로 이동 후 아래 명령을 실행한다. `./api-clients/` 의 json 파일 내용을 확인한다.

```sh
sh run_http2.sh   # client2.py — 기본 http://127.0.0.1:9000 로 h2c 구독요청 (NCOF_TLS=1 이면 https)
```

- 메뉴가 출력되면 `1`(PCF → NCOF) 또는 `2`(RICF → NCOF)를 선택하여 구독 요청을 보낸다.
- 응답 줄에 협상된 프로토콜이 표시된다 — 정상 시 `[응답] HTTP 201 Created (HTTP/2)`.
- 평문 HTTP/1.1 클라이언트가 필요하면 `sh run.sh`(구 `client.py`)를 사용한다.

### 동작 확인

1. 개별 터미널에서 로그를 확인한다.
2. NCOF 로그에서 아웃바운드 SBI·콜백이 `"HTTP/2 201 …"` / `"HTTP/2 204 …"` 로 찍히면 HTTP/2 로 통신 중이다.
3. 필요 시 직접 확인:
   - h2c(기본): `curl --http2-prior-knowledge -v http://127.0.0.1:9000/openapi.json` → `using HTTP/2`
   - TLS(`NCOF_TLS=1`): `curl -k --http2 -v https://127.0.0.1:9000/openapi.json` → `ALPN: server accepted h2`

### 제어 출력 위치 (참고)

NCOF 의 결정 결과는 이를 수신하는 NF 측 콘솔에서 확인한다.

- gNB2 전력 상태(DEEP_SLEEP/ACTIVE): nnef-server(RICF, 9002) — `cell_power_state: ***...***`
- QoS(gbrDl/mbrDl) 변경: callback-server(PCF, 9004) 페이로드의 `qosParamSet`

> 결정은 상태가 바뀔 때만(emit-on-change) 발송되므로, WLAN DL 처리량이 임계(기본 500 Mbps)를 오갈 때 전환이 관찰된다.
