# ncof_generated

3GPP NCOF / NEF / SMF / UPF 와 그 콜백 수신용 서버를 한 번에 띄우는 OpenAPI 기반 FastAPI 스텁 모음.

각 서비스(`nncof`, `nnef`, `nsmf`, `nupf`)와 callback 변형(`*_cb`)은 `openapi.yaml` 로부터 OpenAPI Generator(python-fastapi)로 생성된 코드를 사용합니다. `test_server.py` 는 이 8개 패키지의 라우터를 한 FastAPI 앱에 합쳐 단일 포트(8000)에서 띄워 줍니다.

## 디렉터리 구조

```
ncof_generated/
├── test_server.py          # 통합 실행 엔트리포인트
├── nncof/                  # Producer (NCOF)
├── nncof_cb/               # Callback receiver
├── nnef/, nnef_cb/
├── nsmf/, nsmf_cb/
├── nupf/, nupf_cb/
└── README.md
```

## 사전 준비

- Python 3.10 이상
- `pip` 또는 `uv` (선택)
- 각 패키지의 `requirements.txt` 가 거의 동일하므로 하나만 설치하면 충분

## 설치

```bash
# 1) 가상환경 생성
python3 -m venv .venv
source .venv/bin/activate

# 2) 의존성 설치 (어느 하나만 설치해도 동일)
pip install -r nncof/requirements.txt
```

## 서버 실행

```bash
# 가상환경 활성화 후
python test_server.py
```

또는 활성화 없이 직접:

```bash
.venv/bin/python test_server.py
```

기동 후 콘솔 로그 예시:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

- 기본 바인딩: `0.0.0.0:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## 등록된 라우트

| 구분 | Prefix | 비고 |
|------|--------|------|
| Producer | `/api/nncof` | NCOF 이벤트 구독 / 전송 |
| Producer | `/api/nupf` | UPF 이벤트 노출 |
| Producer | `/api/nnef` | NEF 이벤트 노출 |
| Producer | `/api/nsmf` | SMF 이벤트 노출 |
| Callback | `/callback/nncof` | NCOF notification receiver |
| Callback | `/callback/nupf` | UPF notification receiver |
| Callback | `/callback/nnef` | NEF notification receiver |
| Callback | `/callback/nsmf` | SMF notification receiver |

추가로 페이로드 확인용 echo 엔드포인트가 있습니다 (요청 바디를 그대로 콘솔에 출력):

- `POST /validate/nncof-events-subscription`
- `POST /validate/nncof-events-subscription-notification`
- `POST /validate/nupf-event-exposure-notification`
- `POST /validate/nnef-event-exposure-notification`
- `POST /validate/nsmf-event-exposure-notification`

## 원격 서버에서 실행한 경우 (SSH 포트 포워딩)

원격 GPU 서버에서 띄우고 로컬 브라우저로 보고 싶을 때.

**일반 SSH 접속 환경:**

```bash
ssh -N -L 8000:localhost:8000 <user>@<remote-host>
```

**리버스 SSH 터널로 로컬 `127.0.0.1:2020` 을 거쳐 접속하는 환경:**

```bash
ssh -p 2020 -N -L 8000:localhost:8000 <user>@127.0.0.1
```

옵션 요약:

- `-N` : 셸을 열지 않고 포워딩만 수행
- `-L 8000:localhost:8000` : 로컬 8000 → 원격에서 본 `localhost:8000`
- `-p 2020` : 리버스 터널이 열려 있는 로컬 포트
- `-f` 를 추가하면 백그라운드 실행

로컬 8000번이 이미 점유 중이면 왼쪽 포트만 바꾸면 됩니다 (예: `-L 18000:localhost:8000` → `http://localhost:18000/docs`).

## 종료

서버를 띄운 셸에서 `Ctrl+C`. 백그라운드로 실행했다면:

```bash
pkill -f test_server.py
```

## 트러블슈팅

- **포트 8000 점유**: `ss -ltnp | grep :8000` 으로 확인 후 다른 프로세스 종료 또는 `test_server.py` 내 `uvicorn.run(..., port=...)` 변경.
- **`ModuleNotFoundError: nncof`**: `test_server.py` 가 `sys.path` 를 직접 잡아주므로 리포 루트에서 실행해야 합니다.
- **`security_api.py` import 에러**: `test_server.py` 가 기동 시 자동 패치합니다. 코드 재생성 후에도 동일하게 적용됩니다.

## 코드 재생성

각 서브패키지는 OpenAPI Generator 산출물입니다. 스펙을 수정한 뒤에는 해당 디렉터리에서 generator 를 다시 돌려 재생성한 뒤 `test_server.py` 를 재기동하세요.
