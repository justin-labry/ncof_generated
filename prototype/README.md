# NCOF 

## 사전설치

NOCF 프로젝트 실행을 위해서 아래 사항들을 준비한다.

- uv 설치 (0.6.12)
- python 설치 (3.12.9)
- nodejs 설치 (v24.13.1): UI 개발용

## 환경설정 (.env)

`nncof-server/` 에 `.env` 파일이 필요하다. 제공된 예시를 복사해서 사용한다.

```sh
cd nncof-server
cp .env.example .env
```

> `APP_TITLE` 이 비어 있으면 FastAPI 가 `A title must be provided for OpenAPI` 로 기동에 실패하므로 반드시 값이 있어야 한다.

## 의존성 설치 (uv 워크스페이스)

`prototype/` 는 5개 서버를 멤버로 갖는 uv 워크스페이스이며 하나의 공유 venv 를 사용한다. 최초 1회 전체 동기화한다.

```sh
cd prototype
uv sync --all-packages
```

> 일부 서버는 형제 패키지를 import 한다(예: nnef-server → `nncof_cb`, `nncof`). 공유 venv 에서 특정 서버만 동기화되면 형제 패키지가 제거되어 `ModuleNotFoundError` 가 날 수 있으므로, 위 `uv sync --all-packages` 로 전체를 한 번 설치해 둔다. 각 `run.sh` 는 `uv run --no-sync` 로 실행되어 venv 를 다시 건드리지 않으므로, **최초 1회 전체 동기화 후에는 추가 환경변수 없이 그대로 동작한다.**

## 실행절차

- 5개의 터미널을 실행 후 서브프로젝트별 디렉토리로 이동하여 스크립트를 실행한다.

### 포트 할당 정보

1. NCOF: 8000
2. SMF(UPF): 8001
3. AF: 8002
4. RICF: 8003
5. PCF: 8004

### 실행 방법

```sh
sh run.sh # ./nncof-server
sh run_af.sh # ./nnef-server
sh run_ricf.sh # ./nnef-server (subscription, notification 모두 수행)
sh run.sh # ./nsmf-server (UPF Mockup 도 함께 수행)
sh run.sh # callback-server, NCOF 로부터 notification 수신을 위한 서버 (PCF Mockup 으로 활용)
```
- nnef-server 는 `sh run.sh` 하나로 NEF 목업(AF+RICF 통합, 기본 8002 포트)으로 실행할 수도 있다. (기존 `run_af.sh`/`run_ricf.sh` 분리 실행도 그대로 가능)
- 현재 구현에서 callback-server 는 PCF 가 NCOF로 부터 제어 명령을 수신하는 기능만 제공하고, 구독요청 보내는 기능은 별도의 방법을 이용한다.

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
- UI 는 `/api`, `/subscriptions`, `/api/ws` 요청을 NCOF(`localhost:8000`)로 프록시한다. 따라서 실시간 데이터를 확인하려면 NCOF 서버(8000)가 함께 실행 중이어야 한다.

### 원격(리모트) 접속 시 포트포워딩

리모트 서버에서 실행하는 경우 5173 포트를 로컬로 포워딩한다.

- VS Code / Cursor Remote-SSH: `PORTS` 패널에서 5173 포트를 포워딩하면 자동으로 로컬에서 접속 가능하다. (vite 는 기본 `localhost` 바인딩 그대로 사용)
- 일반 SSH: 로컬에서 `ssh -L 5173:localhost:5173 <user>@<remote-host>` 로 터널을 연 뒤 `http://localhost:5173` 접속.
- Docker 컨테이너에서 실행해 호스트의 published 포트(`-p 5173:5173`)로 접속하는 경우, vite 가 기본 `localhost` 바인딩이면 포트포워딩으로 닿지 않는다. 이때는 `npm run dev -- --host 0.0.0.0` 로 실행한다. (기동 로그에 `Network:` 줄이 보이면 외부 접속 가능 상태)

### 프로덕션 빌드

```sh
npm run build    # 타입체크(vue-tsc) → 빌드 → dist 를 nncof-server/src/nncof/static/ 로 복사
```

빌드 결과물은 NCOF 서버의 정적 파일 경로로 복사되어 `http://localhost:8000` 에서 서빙된다.

## 확인

PCF 또는 RICF 에서 NCOF로 구독요청을 보내기 위해서 Postman, VS Code REST Client Plugin, Python 클라이언트 등을 사용할 수 있다.
- 방법1: VSCode 를 사용하는 경우 확장자가 .http 인 파일을 선택하여 요청을 보낸다.
- 방법2: 터미널에서 client.py 를 실행한다. (추천)

### NCOF로 구독요청 보내기

./api-client/ 로 이동후 아래 명령을 실행한다. ./api-client/의 json 파일의 내용을 확인한다.

```sh
sh run.sh
```
메뉴가 출력되면 1번 또는 2번을 선택하여 구독 요청을 보낸다.

### 동작 확인

1. 개별 터미널에서 로그를 확인한다.

### 제어 출력 위치 (참고)

NCOF 의 결정 결과는 이를 수신하는 NF 측 콘솔에서 확인한다.

- gNB2 전력 상태(DEEP_SLEEP/ACTIVE): nnef-server(RICF) — `cell_power_state: ***...***`
- QoS(gbrDl/mbrDl) 변경: callback-server(PCF) 페이로드의 `qosParamSet`

> 결정은 상태가 바뀔 때만(emit-on-change) 발송되므로, WLAN DL 처리량이 임계(기본 500 Mbps)를 오갈 때 전환이 관찰된다.
