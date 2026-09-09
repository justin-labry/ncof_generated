# NCOF ↔ 두두원(DoDoWon) SBI 연동 — 작업 인수인계

**작성:** 2026-09-09 24:00 KST
**작업 브랜치:** `fix/dodo1-timestamp-fractional-seconds` (main 에서 분기, main 대비 4 커밋 앞섬)

```
31e7fe2  docs(dodo1): 인수인계 문서와 실측 페이로드 보존
55c589f  feat(diag): 임시 관대 수신 계층 추가
131cc03  fix(sbi): targetPeriod 마이크로초 제거
53e8068  fix(sbi): 하위 NF 구독 400 해결
e33cb89  (main 이 있던 지점)
```

미커밋으로 남긴 것은 `prototype/device_info.json` 뿐이다(두두원 IP/포트를 담은 로컬 환경 설정).
**상태:** 제어 루프가 마지막 한 홉만 남기고 전부 연결됨. 남은 블로커는 **두두원 측 IP 오타 1건**.

---

## 1. 한 줄 요약

MODE=DEVICE 로 두두원 장비와 붙였을 때 "PCF/RICF → NCOF 구독 이후 아무 진전이 없던" 문제를
NCOF 측 수정 3건으로 해결했다. 지금은 통지 수신 → 분석 → gNB2 판정까지 정상 동작하며,
**NCOF → PCF/RICF 제어 명령 발송만** 두두원이 알려준 `notificationURI` 의 IP 오타 때문에 실패한다.

---

## 2. 환경

| 구성요소 | 위치 |
|---|---|
| NCOF | `10.254.73.47` — `/home/labry/git/ncof_generated/prototype/nncof-server`, hypercorn h2c :9000 |
| 두두원 sbi_poc_app | `10.254.173.46` — `ssh dodo1` (= `dodo1@10.254.173.46 -p 2299`), `/home/dodo1/SBI/app` |
| NF 주소표 | `prototype/device_info.json` — SMF=55557, AF=55558, RICF=55556, PCF=55555 |

두두원 앱은 **소스가 읽을 수 있다**: `/home/dodo1/SBI/app/{src,include,config,templates,send_json}`.
`send_json/` 에는 두두원이 **송신 직전에 남기는 디버그 덤프**가 쌓이므로, "두두원이 실제로 무엇을
보냈는가" 를 확인하는 가장 빠른 방법이다.

> ⚠️ 두두원 장비는 **읽기 전용**으로만 다룰 것. 앱 재시작·요청 주입·DB 접근 금지.

### 기동

```bash
# NCOF (관대 수신 진단 계층 포함)
cd /home/labry/git/ncof_generated/prototype/nncof-server && NCOF_LENIENT_INGEST=1 sh run_http2.sh

# 두두원 (사용자가 직접)
ssh dodo1 -> cd /home/dodo1/SBI/app && ./sbi_poc_app
```

`MODE=DEVICE` 는 셸에 export 되어 있어야 한다. `NCOF_LENIENT_INGEST` 를 빼면 관대 수신이 완전히
비활성화된다(미들웨어가 아예 설치되지 않음).

---

## 3. 두두원 장비의 결정적 특성 — 이걸 모르면 전부 헤맨다

**두두원은 JSON 스키마 검증을 하지 않는다. 본문 substring 매칭으로 메시지 종류를 판별한다.**
`/home/dodo1/SBI/app/src/ncof_flow_common.cpp` 의 `Detect_Ncof_Recv_Json_Type()` (:391~:488):

```c
NcofRecvJsonType Detect_Ncof_Recv_Json_Type(const std::string& path, const std::string& body) {
    (void)path;                                   // ← HTTP 경로는 즉시 폐기한다
    if (has("eventsSubs") && (has("_POWER_ENERGY_CONSUMPTION") || has("_RF_SIGNAL"))) return 2P;
    if (has("serviveName") && has("nsmf-event-exposure"))                             return 3계열;
    if (has("eventsSubs") && has("DISPERSION"))                                       return 6P;
    if (has("eventsSubs") && has("PERF_DATA") && has("dap-001"))                      return 4계열;
    if (has("eventsSubs") && has("PERF_DATA") && has("dap-002"))                      return 5계열;
    ...
    return NCOF_RECV_UNKNOWN;                     // → 핸들러가 400 반환
}
```

- **경로(이중 슬래시 `//subscriptions` 포함)는 400 과 무관하다.**
- 3 계열 내부에서 다시 `"gNbId"`/`"n3IwfId"`/`"subId"`/`"altNotifFqdns"` **키의 존재 여부**로
  3 / 3P / 7 / 7P 를 가른다(:416~:455, `Is_7p_Nsmf_Event_Exposure` :200~:218).
  NCOF 가 `jsonable_encoder` 를 `exclude_none` 없이 호출해 **값이 null 인 키까지 실어 보내므로**
  이 분기가 의도와 다르게 잡힌다.
- **UPF 사용량 리포트(`8_` 계열)는 오직 kind 3/3p 에서만 나온다.** 7/7p 는 `12_c`/`12p_c` 를 보낸다.
- 400 응답 본문은 언제나 `{"error":"bad request"}` 고정 — 이유를 알려주지 않는다.
  실제 사유는 stderr(`log_message`)에만 남고 파일로 저장되지 않는다.
- 구독 성공 시 **200** 을 주고 본문은 `{"result":"ok"}` 뿐. `subscriptionId`/`subId`/`Location`/
  `Subscription-ID` 를 **전혀 주지 않는다**(`http2_server.cpp:372-375`).
  따라서 NCOF 로그의 `… 로부터 ID 를 획득하지 못함 (Status: 200)` 은 **정상이며 없앨 수 없다.**

---

## 4. 오늘 한 수정

### 커밋 `53e8068` — 하위 NF 구독 400 해결

`prototype/nncof-server/src/nncof/core/subscription_request_builder.py`

| 위치 | 변경 | 효과 |
|---|---|---|
| `:248` | `servive_name` 값 `"nsmf-event_exposure"`(밑줄) → `"nsmf-event-exposure"`(하이픈) | SMF 향 2건(#2,#6) 400 해소 |
| `:464-465` | `af_event_exposure.data_acc_prof_id = "dap-001"` / `ricf_… = "dap-002"` 추가 | AF/RICF PERF_DATA 2건(#3,#4) 400 해소 |
| `:467` | `ricf_event_exposure.supp_feat = "FF"` 추가 | 대칭성(400 과 무관) |
| `:346`, `:525` | `"PEF_FLOW"` → `"PER_FLOW"` | TS 29.508 enum 준수(**400 원인 아니었음**) |

> 키 이름의 오타 `servive` 는 **그대로 두어야 한다** — 두두원도 `"serviveName"` 으로 찾는다.
> 양측이 같은 오타를 공유하는 상태다.

### 커밋 `131cc03` — UPF 주기 리포트 미수신 해결 (핵심)

`subscription_request_builder.py` `_build_target_period()` (:67~)

두두원의 ISO8601 파서(`ncof_flow_subscription_core.cpp:226`)는

```c
sscanf(t, "%d-%d-%dT%d:%d:%d%c%d:%d")
```

인데, **소수 초가 있으면 반환값이 9 가 아니라 8** 이 되어 `:245` 의 `if (ret == 9)` 오프셋 보정이
건너뛰어진다 → KST 벽시계를 UTC 로 간주 → `start_epoch` 이 정확히 **+9시간 미래** →
스케줄러가 그 시각으로 예약 → 리포트가 사실상 오지 않음.

```python
_DODO1_NO_FRACTIONAL_SECONDS = True          # 두두원 파서 고쳐지면 False
_DODO1_START_BACKDATE = timedelta(seconds=60)
...
    start = (now - _DODO1_START_BACKDATE).replace(microsecond=0)
    stop = stop.replace(microsecond=0)
```

`targetPeriod` 를 싣는 구독은 SMF 향 2건뿐이고, 두두원에서 `start_epoch` 을 계산하는 핸들러도
3/3p·7/7p 뿐이라 두 집합이 겹쳐 **"NEF 통지 4종은 오는데 UPF 계열만 0건"** 이라는 증상이 나왔다.

**검증:** 적용 후 두두원이 `8_NotificationData_from_UPF_to_NCOF_v1.0.tmpl` 을 60초 주기로 발송 시작
(23:35:15 최초 확인).

### 커밋 `55c589f` — 관대 수신 진단 계층 (패치 B)

- **신규** `prototype/nncof-server/src/nncof/core/lenient_ingest.py` (402줄)
- **수정** `prototype/nncof-server/src/nncof/main.py` — import 1줄 + `install_lenient_ingest(app)` 1줄

`NCOF_LENIENT_INGEST=1` 일 때만 활성화되는 **순수 ASGI 미들웨어**. 두두원 통지의 스키마 위반을
전부 기록하고, 알려진 결함을 수리해 정상 라우트로 흘려보낸다.

핵심은 **오류 주도 수리** — 필드명을 추측하지 않고 모델이 낸 오류 지점에 후보값을 넣어보고
오류가 사라지는 것을 채택한다. 그래서 규격이 제각각인 필드가 자동으로 구분된다:

| 액션 | 예 |
|---|---|
| `DROP_SENTINEL` | `dlAverageThroughput: "-999"` → 필드 삭제 |
| `STRINGIFY_BITRATE_BPS` | `150000000` → `"150000000 bps"` |
| `STRINGIFY_PACKETRATE_PPS` | `500000` → `"500000 pps"` |
| `STRINGIFY_VOLUME_BYTES` | `9000000000` → `"9000000000 B"` |
| `ROUND_TO_INT` / `CEIL_TO_INT` | `pdb: 0.45` → `1` |

> 🔴 **`STRINGIFY_BITRATE_BPS` 를 함부로 건드리지 말 것.**
> `decide_wlan_gnb2_rule._parse_mbps()` 는 **단위 접미사가 없으면 Mbps 로 간주**한다.
> 두두원이 보내는 bps 정수를 단위 없이 통과시키면 metric 이 10⁶배 부풀려져
> (`300,000,000 Mbps`) gNB2 가 영구 ACTIVE 로 고정된다. `bps` 명시가 이를 막는 유일한 방법이다.

**출력:** `prototype/nncof-server/logs/lenient_ingest/`
- `ledger.jsonl` — 위반·수리 전수 원장 (두두원 보고서 원본 데이터)
- `*.raw.json` — 수리 전 원본 보존

**OFF 검증 완료:** 환경변수 없으면 미들웨어 0개, 기존 동작 그대로(422), 덤프 디렉터리도 안 만듦.

---

## 5. 현재 파이프라인 상태

| 단계 | 상태 |
|---|---|
| PCF/RICF → NCOF 구독 | ✅ |
| NCOF → SMF/AF/RICF 팬아웃 10건 | ✅ 전부 HTTP/2 200 |
| 두두원 → NCOF 통지 발송 | ✅ 60초 주기 (`8_`, `9_`, `10_a`, `11p_b`, `12p_c`, `13p_d`) |
| NCOF 수신·파싱 | ✅ 관대 수신으로 통과 (`13p_d` 만 422 — 의도된 것) |
| 저장 → 분석 → gNB2 판정 | ✅ `분석 메트릭 WLAN_DL_MBPS:150.0` → `CELL_POWER_STATE: DEEP_SLEEP` |
| NCOF → PCF/RICF 제어 발송 | ❌ **`All connection attempts failed`** |

`fail to retrieve wlan performance data...` 는 23:48 기동 이후 **0건**.

### 마지막 블로커 (실측 확인)

```
두두원이 준 notificationURI : http://10.254.73.46:55555/   ← 173 이 아니라 73
두두원 SBI 실제 주소        : http://10.254.173.46:55555/

10.254.73.46   :55555 연결 실패 (ping 무응답, 존재하지 않는 호스트)
10.254.173.46  :55555 연결 성공
```

NCOF 의 `_notify_subscriber()`(`subscription_handler.py:195-212`)는 **구독자가 준 URI 를 그대로**
사용한다(nrf 조회 안 함). 두두원 구독 페이로드의 IP 오타가 원인이다.

---

## 6. 두두원 수정 요청 목록

| 심각도 | 항목 | 근거 |
|---|---|---|
| **치명** | 구독 `notificationURI` IP 오타 `10.254.73.46` → `10.254.173.46` | 제어 명령 미도달 |
| **치명** | ISO8601 소수 초 미지원 (`ncof_flow_subscription_core.cpp:226` sscanf) — TS 29.571 DateTime 은 소수 초 허용 | 현재 NCOF 가 우회 중 |
| **높음** | throughput 을 bps **정수**로 전송 → `"150000000 bps"` 형식 **문자열** 필요 | 10⁶배 오차 |
| **높음** | `-999` 센티넬 — 값 없으면 **필드 생략**이 규격 | `pdb`, `plr*`, `_delayUl`, `_maxRtt`, `totalVolume` 등 |
| **높음** | 정수 필드에 소수 | `pdb: 0.45`, `_dlMaxPacketDelay: 20.74` |
| **높음** | Volume 필드가 정수 → `"9000000000 B"` 형식 필요 | 바이트 단위 정규식 |
| 중간 | `13p_d`: `timeStamp`→`timestamp` 오타, `_nodeAddrs` 배열/객체 불일치, `nrLocation.tai`/`ncgi` 누락, `nrCellId="cell-002"` 가 `^[A-Fa-f0-9]{9}$` 위반 | 자동 수리 불가 |
| 중간 | AF 템플릿과 RICF 템플릿의 값 생성 규칙이 서로 다름(`9_` 는 `-999`, `10_a` 는 소수) | 한 번에 고치려면 둘 다 |
| 낮음 | `templates/send/` 의 공백 든 중복 파일 `8p_..._v1.0 _USER_DATA_USAGE_MEASURES.tmpl` 정리 | 참조되지 않는 잔재 |

전체 원장: `logs/lenient_ingest/ledger.jsonl` (샘플은 `captured/lenient_ledger_sample.jsonl`)

---

## 7. ⛔ 이미 반증된 가설 — 다시 파지 말 것

| 가설 | 판정 |
|---|---|
| `PEF_FLOW` 오타가 400 의 원인 | ❌ 두두원 소스에 `granularityOfMeasurement` 참조 자체가 없음. 수정은 규격 준수 차원 |
| 이중 슬래시 `//subscriptions` 가 400 의 원인 | ❌ `Detect_Ncof_Recv_Json_Type` 이 `(void)path;` 로 경로를 폐기 |
| 방화벽/ufw 가 콜백을 막는다 | ❌ `journalctl -k` 에 `10.254.173.46` 발 `DPT=9000` 차단 0건. TCP 연결 실측 성공 |
| HTTP/2 h2c 협상 문제 | ❌ 200 응답이 `HTTP/2` 로 정상 협상됨 |
| 7P 핸들러가 `8p_` 를 보내야 정상 | ❌ 7/7p 는 `12_c`/`12p_c` 만 보냄. `8_` 계열은 kind 3/3p 전용 |
| `exclude_none=True` 가 UPF 리포트를 살린다 | ❌ #6 이 7P→7 로 옮겨갈 뿐 같은 9시간 벽. 별개 이슈로만 가치 있음 |
| 템플릿 파일명 공백이 원인 | ❌ 코드가 참조하는 공백 없는 이름이 실제로 존재 |
| `notifUri` 가 NCOF 에 도달 못 한다 | ❌ 도달함. `10.254.73.47:9000` 으로 연결 실측 확인 |
| NEF 422 를 고치면 결정 루프가 돈다 | ❌ `data_analyzer.py:184-185` 가 `NefEventExposureNotif` 를 배제. UPF `NotificationData` 만 소비 |

---

## 8. 다음 할 일

### ⭐ 가장 먼저 할 일 — 두두원에 `notificationURI` IP 오타 수정 요청

두두원이 구독에 실어 보내는 `notificationURI` 가 `http://10.254.73.46:55555/` 인데
실제 주소는 `http://10.254.173.46:55555/` 다. **`173` 에서 `1` 이 빠진 한 글자 오타**이며,
이것 하나가 지금 유일하게 남은 블로커다(§5 참조). 나머지 단계는 전부 통과 상태이므로,
이 한 글자만 고쳐지면 제어 루프가 닫힐 가능성이 높다.

`_notify_subscriber()` 는 nrf 조회를 하지 않고 **구독자가 준 URI 를 그대로** 쓰기 때문에
NCOF 설정으로는 우회되지 않는다. PCF(55555)·RICF(55556) 두 구독 모두 해당된다.

### 그 다음

1. **NCOF 임시 URI 재작성 (회신 대기 중 병행)** — `_notify_subscriber()`
   (`core/subscription_handler.py:195-212`) 에서 `10.254.73.46` → `10.254.173.46` 치환.
   패치 A(`_DODO1_NO_FRACTIONAL_SECONDS`) 와 같은 TEMP 플래그 방식으로 넣을 것.
   두두원 회신을 기다리지 않고 **오늘 안에 종단 루프를 완주**해 볼 수 있다.
   확인 지점: 제어 명령이 두두원에 도달하는지 → RICF 가 다음 주기 `13p_d` 통지에서
   `cell_power_state` 를 에코하는지(`ncof_flow_dynamic_report.cpp` 의 gNB2 전력 반영).
2. **두두원에 §6 나머지 목록 전달** — `-999` 센티넬, bps 정수, 소수 정수필드, `13p_d` 구조 결함.
   `logs/lenient_ingest/ledger.jsonl` 이 근거 데이터다.
3. 확인 사항: 두 구독의 metric 이 각각 `0.0` / `150.0` 로 갈린다. 한쪽 store 에 UDUM 이
   없는지 확인 필요(`12p_c` 만 들어간 구독일 가능성).
4. 두두원이 소수 초 파싱을 고치면 `_DODO1_NO_FRACTIONAL_SECONDS = False` 로 되돌리고 재검증.
5. 연동이 안정화되면 관대 수신 계층(`NCOF_LENIENT_INGEST`)을 끄고, 최종적으로
   `core/lenient_ingest.py` 와 `main.py` 의 2줄을 제거.

---

## 9. 참고 자료

- `captured/` — 두두원이 실제로 보낸 본문(`8_`, `9_`, `10_a`, `11p_b`, `13p_d`, 구독 `1_`/`1p_`)과
  NCOF 가 보낸 하위 구독 6건(`payload_1..6.json`). **스키마 대조·회귀 검증에 그대로 쓸 수 있다.**
- `captured/lenient_ledger_sample.jsonl` — 관대 수신 원장 샘플 12건

### NCOF 핵심 파일

| 파일 | 역할 |
|---|---|
| `core/subscription_request_builder.py` | 하위 NF 구독 생성. 오늘 수정의 대부분이 여기 |
| `core/subscription_handler.py` | 팬아웃 POST(`:113-152`), 제어 발송(`:195-212`), `_httpx_kwargs`(`:34-42`) |
| `core/data_analyzer.py` | 주기 분석. `:184-185` 가 UPF 만 통과시킴, `:316-317` 광범위 except |
| `core/decide_wlan_gnb2_rule.py` | `_parse_mbps`(`:160`), `extract_wlan_dl_mbps`(`:173`), `TH_MBPS=500.0` |
| `core/lenient_ingest.py` | 관대 수신 (임시) |
| `core/nrf.py` | `MODE=DEVICE` 시 `device_info.json` 로드 |

### 두두원 핵심 소스

| 파일 | 역할 |
|---|---|
| `src/ncof_flow_common.cpp:391-488` | 메시지 종류 판별(substring 매칭) |
| `src/ncof_flow_subscription_core.cpp:208-259` | ISO8601 파서 (소수 초 버그) |
| `src/ncof_flow_subscription_core.cpp:905-981` | 주기 송신 스케줄러 |
| `src/ncof_flow_subscription_handlers.cpp:26-190` | kind 3/3p 핸들러 (`8_` 템플릿 선택) |
| `src/http2_server.cpp:372-379` | 200/400 응답 생성 |
