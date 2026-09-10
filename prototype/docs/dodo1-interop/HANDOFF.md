# NCOF ↔ 두두원(DoDoWon) SBI 연동 — 작업 인수인계

**작성:** 2026-09-09 24:00 KST · **갱신:** 2026-09-10 17:30 KST
**작업 브랜치:** `fix/dodo1-timestamp-fractional-seconds` (main 에서 분기, main 대비 10 커밋 앞섬)

```
(HEAD)   fix(sbi): 패치 C 제거 — 두두원이 notificationURI 오타를 고침
81c6689  docs(dodo1): §6.1/§6.2 신설
55b3fcb  docs(dodo1): 14_e 봉투 수정 실기동 검증
1335888  fix(control): 14_e 제어 본문의 템플릿 고정 신원·시각 제거
95f9ed1  docs(dodo1): 제어 루프 관통 확인 및 "RICF 에코" 전제 반증 반영
f614abd  fix(sbi): notificationURI 오타 IP 발송 직전 치환 (패치 C, TEMP)
4a9c8f0  docs(dodo1): HANDOFF 커밋 상태 갱신
31e7fe2  docs(dodo1): 인수인계 문서와 실측 페이로드 보존
55c589f  feat(diag): 임시 관대 수신 계층 추가            (패치 B)
131cc03  fix(sbi): targetPeriod 마이크로초 제거          (패치 A)
53e8068  fix(sbi): 하위 NF 구독 400 해결
e33cb89  (main 이 있던 지점)
```

미커밋으로 남긴 것은 `prototype/device_info.json` 뿐이다(두두원 IP/포트를 담은 로컬 환경 설정).

**상태: 제어 루프가 닫혔고, 임시 패치 C 는 회수 완료.** 2026-09-10 09:39 에 전 구간을 관통했고,
17:16 에 **두두원이 `notificationURI` 오타를 고쳐** 패치 C 없이 제어 명령이 양쪽 200 으로 도달함을
재확인했다(치환 로그 0건). 남은 임시 패치는 **A(소수 초)와 B(관대 수신)** 둘이며,
**차단성 블로커는 없다.**

---

## 1. 한 줄 요약

MODE=DEVICE 로 두두원 장비와 붙였을 때 "PCF/RICF → NCOF 구독 이후 아무 진전이 없던" 문제를
NCOF 측 수정 4건(패치 A·B·C + 구독 400 수정)으로 해결했다. 제어 루프 전 구간이 관통되며,
NCOF 가 보낸 `_cellPowerState: DEEP_SLEEP` 제어 명령을 두두원이 200 으로 수락한다.

다만 **"RICF 가 cell_power_state 를 에코한다" 는 전제는 사실이 아니었다** — 두두원에는 에코 기능이
아예 없다(§5 참조). 제어 명령의 실제 종착지는 리포트 필드가 아니라 **물리 gNB2 의 cell-stop/cell-start** 다.

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
    // ⚠️ 아래 두 분기가 가장 먼저 온다 — NCOF→두두원 "제어 명령" 이 여기로 갈린다 (:395~:404)
    if (has("eventNotifications") && has("QOS_POLICY_ASSIST")
                                  && has("qosPolAssistInfos"))            return 14  (NCOF→PCF);
    if (has("eventNotifications") && (has("_CELL_POWER_CTRL")
                                  ||  has("_cellPowerCtrlOptInfos")
                                  ||  has("_cellPowerParamSet")
                                  ||  has("_cellPowerState")))            return 15F (NCOF→RICF);
    // ↓ 이하가 두두원→NCOF 구독 계열
    if (has("eventsSubs") && (has("_POWER_ENERGY_CONSUMPTION") || has("_RF_SIGNAL"))) return 2P;
    if (has("serviveName") && has("nsmf-event-exposure"))                             return 3계열;
    if (has("eventsSubs") && has("DISPERSION"))                                       return 6P;
    if (has("eventsSubs") && has("PERF_DATA") && has("dap-001"))                      return 4계열;
    if (has("eventsSubs") && has("PERF_DATA") && has("dap-002"))                      return 5계열;
    ...
    return NCOF_RECV_UNKNOWN;                     // → 핸들러가 400 반환
}
```

> 📌 **2026-09-10 정정.** 이 문서의 이전 판은 위 두 분기를 누락하고 `(void)path;` 로 시작한다고 적었다.
> 실제로는 (a) **14/15F 제어 분기가 맨 앞에 온다**, (b) 경로를 통째로 버리지는 않는다 —
> **5/5p 를 가르는 한 분기만은 `path` 를 읽는다.** 나머지 분기에 대해서는 경로 무관이 맞다.

- **경로(이중 슬래시 `//subscriptions` 포함)는 400 과 무관하다.**
- **포트는 라우팅에 전혀 영향이 없다.** `main.cpp:277-306` 이 55555/55556/55557/55558 네 포트를
  모두 같은 `Start_Http2_Server` 로 띄우고, 전부 `http2_server.cpp:369-370` 의 단일 디스패처를 탄다.
- **제어 명령의 실패 응답은 400 이 아니라 500 이다.** 본문이 14/15F 로 라우팅됐지만 대상이 0건이면
  핸들러가 0 을 반환하고 `ncof_flow_subscription_handlers.cpp:761-784` 가 500 을 준다.
  NCOF 는 200/204 외 전부를 실패로 처리하므로(`subscription_handler.py:248`) 로그에 `제어명령 실패`
  로 남는다. **즉 제어 명령을 디버깅할 때 500 은 "라우팅은 됐다" 는 신호다.**
- 두두원에는 **14_e / 15f 수신용 템플릿이 없다**. `templates/` 아래에는 `send/` 19개(전부 송신용)뿐이고,
  수신 제어는 필드 단위로 직접 파싱한다. NCOF 가 맞춰야 할 템플릿 계약은 존재하지 않는다.
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

### 커밋 `f614abd` — notificationURI 오타 IP 치환 (패치 C, TEMP) → **2026-09-10 17:30 제거됨**

`core/subscription_handler.py` — 모듈 상수 + 헬퍼 + `_notify_subscriber()` 3줄.

```python
_DODO1_NOTIF_URI_REWRITE: dict[str, str] = {"10.254.73.46": "10.254.173.46"}
# 되돌리기: 이 딕셔너리를 {} 로 비우면 끝.
```

- `urlsplit` 으로 **호스트만** 교체한다(경로·쿼리에 같은 문자열이 있어도 안 건드림).
- **발송 직전 URL 에만** 적용한다. `self.subscription.notification_uri` 원본은 보존되므로
  구독 조회 응답·상태 파일에는 두두원이 보낸 값이 그대로 남고, **두두원이 오타를 고치면 별도 조치 없이
  바른 주소가 쓰인다**(치환 대상이 아니면 원본 통과).
- 치환이 실제로 발동하면 `WARNING … TEMP 두두원 우회: 제어명령 대상 URI 치환` 을 남긴다 —
  임시 패치의 존재를 로그에서 숨기지 않기 위함.

**검증:** 헬퍼 단위 8케이스(오타 IP·포트 유무·https·경로 내 동일 문자열·이미 올바른 IP·NCOF 자신·
localhost) 전수 통과 + `_notify_subscriber()` 를 httpx 목으로 호출한 오프라인 4케이스 전수 통과 +
아래 §5 의 실기동 종단 확인.

> ✅ **회수 완료 (2026-09-10 17:30).** 두두원이 `poc_test.ncof_sub_profile` 의 `uri_pcf`/`uri_ricf` 를
> `10.254.173.46` 으로 수정했다. 패치 C 를 끈 상태로 재검증해 **치환 없이** 제어 명령이 양쪽 200 으로
> 도달함을 확인하고(17:16:56 PCF / 17:16:59 RICF, `TEMP 두두원 우회` 0건,
> `All connection attempts failed` 0건), 상수·헬퍼·호출부를 전부 제거했다.
> 파일은 패치 C 도입 이전 블롭(`1c15998`)과 바이트 단위로 동일하다.
>
> **오타의 출처(재발 시 여기를 보라):** 토큰 `__URI_PCF__`/`__URI_RICF__` →
> `ncof_send_templates.cpp:183-184` 이 `config.uri_pcf/uri_ricf` 로 치환 →
> `db.cpp:3725` 가 `poc_test.ncof_sub_profile WHERE profile_id='DEFAULT'` 에서 읽음
> (`profile_id` 는 `config/6g.config` 의 `PROFILE`). **프로파일은 기동 시 1회만 읽으므로 앱 재시작 필요.**
> `send_json/` 은 `Save_Json_Debug_Files()`(`app_util.cpp:145`)가 남기는 **송신 덤프(출력)** 이므로
> 거기를 고치는 것은 아무 효과가 없다 — 소스 전체에서 읽는 코드가 없다.
> `poc_test.sql` 덤프의 시드값은 `https://6g-i2p.etri.re.kr/poc2/pcf/` 라 오타와 무관하지만,
> 재적재하면 그 FQDN 으로 되돌아가 또 안 붙는다.

> `_notify_subscriber()` 가 NCOF 에서 **구독자 제공 URI 로 실제 요청을 보내는 유일한 지점**이다.
> `NncofEventsSubscription` 에는 `altNotifFqdns`/`altNotifIpAddrs` 필드 자체가 없고
> (그건 NCOF 가 *보내는* NSMF 모델에만 있으며 NCOF 는 채우지 않는다),
> 나머지 읽기 지점 2곳(`subscription_manager.py:333`, `utils.py:135→:187`)은 GUI 에코일 뿐이다.
> 따라서 **다른 곳에 오타 IP 가 남아 요청이 새는 경로는 없다.**

---

## 5. 현재 파이프라인 상태 — **제어 루프 관통 완료 (2026-09-10 09:39 실측)**

| 단계 | 상태 |
|---|---|
| PCF/RICF → NCOF 구독 (09:38:29 / 09:38:30) | ✅ 핸들러 2건 기동 |
| NCOF → SMF/AF/RICF 팬아웃 10건 | ✅ 전부 HTTP/2 200 |
| 두두원 → NCOF 통지 발송 | ✅ 60초 주기 (`8_`, `9_`, `10_a`, `11p_b`, `12p_c`, `13p_d`) |
| NCOF 수신·파싱 | ✅ 관대 수신으로 통과 (`13p_d` 만 422 — 의도된 것) |
| 저장 → 분석 → gNB2 판정 | ✅ `분석 메트릭 WLAN_DL_MBPS:150.0` → `CELL_POWER_STATE: DEEP_SLEEP` |
| ~~TEMP URI 치환 (패치 C)~~ | ✅ **불필요** — 두두원이 오타를 고쳐 17:30 제거 (§4) |
| **NCOF → PCF 제어 발송 (09:39:30)** | ✅ **HTTP 200 수락** |
| **NCOF → RICF 제어 발송 (09:39:34)** | ✅ **HTTP 200 수락** (`_cellPowerState: DEEP_SLEEP`, `gNBValue: 000002`) |
| RICF 가 `cell_power_state` 를 에코 | ⛔ **에코 기능이 존재하지 않는다** (아래) |

`fail to retrieve wlan performance data...` 는 계속 **0건**.
실제 전송 본문은 `captured/14_e_control_NCOF_to_PCF_sent_2026-09-10_pretty.json` 과
`captured/15_f_control_NCOF_to_RICF_sent_2026-09-10_pretty.json` 에 보존했다.

### ⛔ "RICF 가 cell_power_state 를 에코한다" 는 전제가 틀렸다 — 조사 종료

이전 판 §8 은 종단 확인 지점을 "다음 주기 `13p_d` 에서 `cell_power_state` 에코" 로 잡았다.
**그런 기능은 두두원에 없다.** 실측·소스 양쪽으로 확정했다.

- `13p_d` 의 `_powerState` 는 템플릿 하드코딩 리터럴이다 —
  `templates/send/13p_d_….tmpl:149`, `:183` 에 `"_powerState": "ACTIVE"` 로 박혀 있다.
  제어 명령을 200 으로 수락한 **직후 주기에도 값이 그대로 `ACTIVE`** 임을 실측했다(09:39:34 수락 → 09:40:31 리포트).
- 15F 수신 경로(`ncof_flow_control.cpp:487-543`)의 부수효과는 정확히 셋뿐이다:
  1. `INSERT INTO gnb_control_recv` (`db.cpp:287`)
  2. `INSERT INTO gnb_control` (`db.cpp:336`)
  3. `sshpass … ssh root@<gnb2_ip> 'python3 /home/tetra/euGNB/scripts/eu.gnbControl.py cell-stop|cell-start'`
     (`gnb_ssh_control.cpp:109`, `:156`, `:160`)
- 두 테이블은 **코드 어디에서도 SELECT 되지 않는다**(참조는 위 INSERT 2개뿐). 인메모리 상태도 바뀌지 않는다.
  따라서 다음 리포트를 만드는 `ncof_flow_dynamic_report.cpp` 는 제어 명령의 영향을 받을 수가 없다.
- 두두원은 **제어 명령을 받아도 `send_json/` 에 아무것도 쓰지 않는다**(그 디렉터리는 송신 덤프 전용).
  수신 본문은 MySQL `poc_test.recvJson` 에만 들어가고 파일로 남지 않는다.

**결론: 제어 루프의 실제 종착지는 리포트 필드가 아니라 물리 gNB2 의 cell-stop/cell-start 다.**

> ⚠️ **HTTP 200 은 gNB2 가 실제로 제어됐다는 증거가 아니다.**
> 15F 핸들러의 `save_count` 는 **MySQL INSERT 성공만으로** 증가하며, SSH 셸아웃보다 앞서고
> 그 성공 여부와 무관하다. 200 이 보장하는 것은 "두두원이 파싱·라우팅·기록했다" 까지다.
> SSH 실행 결과는 두두원 stderr 나 gNB2 호스트에서만 확인 가능하며, **읽기 전용 제약 때문에 이번에 미확인**이다.
> (다만 SSH 분기는 `gNBValue` 가 정확히 `"000002"` 여야 타는데, NCOF 페이로드는 이 조건을 만족한다.)

### 분석 메트릭이 주기마다 튄다 (0.0 / 150.0 / 300.0)

이전 판 §8-3 의 "두 구독의 metric 이 0.0 / 150.0 로 갈린다" 는 **구독 간 차이가 아니라 주기 간 진동**이다.

- NCOF 는 구독 1건마다 **UPF 스트림을 2개** 만든다(SERVICE_EXPERIENCE, WLAN_PERFORMANCE).
  둘 다 `/notifications/upf/<sub_id>` 로 오고(`subscription_request_builder.py:257`),
  같은 store 에 **서로 다른 correlationId 로** 쌓인다(`data_store.py:42`, `subscription_handler.py:369-370`).
- `_get_wlan_performance_data()`(`data_analyzer.py:213-227`)가 **UDUM `timeStamp` 가 가장 최신인 것 하나**를
  고르는데, 두 스트림의 주기가 다르다(SERVICE_EXPERIENCE 60초 / WLAN_PERFORMANCE 120초).
  → 주기마다 어느 쪽이 최신이냐가 바뀌어 metric 이 고정된 두 값 사이를 오간다.
- `0.0` 은 "선택된 통지의 `dlAverageThroughput` 이 전부 `-999` 센티넬이라 관대 수신이 필드를 지웠다" 는 뜻이다.
- **`0.0` 은 무해하지 않다.** PCF 구독에서 `0.0` 이 DEEP_SLEEP 판정을 만들고 그게 PCF 향 QoS 정책
  제어 명령으로 나갔다. 다만 `data_analyzer.py:269` 의 nf_type 게이트가 PCF 를 cell-power 분기에서
  막아 주므로 gNB2 전력 판정 자체가 오염되지는 않는다.
- **오늘의 판정은 어느 값이어도 같다** — 0.0 / 150.0 / 300.0 전부 `TH_MBPS=500.0` 미만이라 모두 DEEP_SLEEP.
  즉 지금 당장 오판을 만들지는 않지만 잠재 결함이다.
- 덧붙여 **150.0 도 300.0 도 실측값이 아니다.** 회선 위의 비-센티넬 throughput 은 전부 템플릿 상수다.

---

## 6. 두두원 수정 요청 목록

| 심각도 | 항목 | 근거 |
|---|---|---|
| ~~치명~~ **해결** (2026-09-10 17:16) | ~~구독 `notificationURI` IP 오타~~ — 두두원이 `poc_test.ncof_sub_profile.uri_pcf/uri_ricf` 를 `10.254.173.46` 으로 수정. 패치 C 회수 완료 | 치환 없이 양쪽 200 재확인 |
| **치명** | ISO8601 소수 초 미지원 (`ncof_flow_subscription_core.cpp:226` sscanf) — TS 29.571 DateTime 은 소수 초 허용 | 현재 NCOF 가 우회 중 |
| **높음** | throughput 을 bps **정수**로 전송 → `"150000000 bps"` 형식 **문자열** 필요 | 10⁶배 오차 |
| **높음** | `-999` 센티넬 — 값 없으면 **필드 생략**이 규격 | `pdb`, `plr*`, `_delayUl`, `_maxRtt`, `totalVolume` 등 |
| **높음** | 정수 필드에 소수 | `pdb: 0.45`, `_dlMaxPacketDelay: 20.74` |
| **높음** | Volume 필드가 정수 → `"9000000000 B"` 형식 필요 | 바이트 단위 정규식 |
| **높음** | `13p_d` 계열 구조적 결함 5종 → **§6.1 에 경로·건수·규격 근거 정리** | 자동 수리 불가, `13p_d` **100% 거절 중** |
| 중간 | AF 템플릿과 RICF 템플릿의 값 생성 규칙이 서로 다름(`9_` 는 `-999`, `10_a` 는 소수) | 한 번에 고치려면 둘 다 |
| 낮음 | `templates/send/` 의 공백 든 중복 파일 `8p_..._v1.0 _USER_DATA_USAGE_MEASURES.tmpl` 정리 | 참조되지 않는 잔재 |
| 중간 | **제어 명령 수용 결과를 관측할 방법이 없다** — 수신 15F 는 `poc_test.recvJson`/`gnb_control*` 로만 들어가고 어디서도 SELECT 되지 않으며, `send_json/` 에도 안 남는다. 최소한 수신 덤프 1개라도 파일로 남겨 주면 연동 검증이 가능해진다 | 종단 확인 불가 |
| 중간 | **HTTP 200 이 실제 gNB 제어 성공을 뜻하지 않는다** — `save_count` 는 MySQL INSERT 만으로 증가하고 SSH 셸아웃 결과를 반영하지 않는다. 셸아웃 실패를 응답 코드에 반영해 달라 | 무증상 실패 |
| 낮음 | `13p_d` 의 `_powerState` 가 템플릿 하드코딩 `"ACTIVE"`(:149, :183). 제어 반영 상태를 여기에 실어 주면 NCOF 가 폐루프를 자체 검증할 수 있다 | 폐루프 검증 |
| 낮음 | 400 응답에 사유를 실어 달라(현재 `{"error":"bad request"}` 고정, 사유는 stderr 에만) | 왕복 비용 |
| **높음** | **하위 구독 응답에 구독 ID 가 없다** — 본문은 `{"result":"ok"}` 뿐이고 헤더는 `:status`/`content-type`/`server` 뿐(`http2_server.cpp:78-85`, `:257-271`). uuid4 를 발급해 **`Subscription-ID` 응답 헤더**로 실어 달라(본문 구조 변경 불필요). 저장소의 mock NF 3종과 NCOF 자신의 northbound 는 모두 이 헤더 규약을 지킨다 | **§6.2** — 고아 구독 누적 |

### NCOF 측 자체 결함 (두두원과 무관, 우리가 고칠 것)

| 심각도 | 항목 | 근거 |
|---|---|---|
| ~~높음~~ **해결** (`1335888`) | ~~14_e(PCF 향) 제어 본문이 템플릿의 하드코딩 값을 그대로 내보낸다~~ — `apply_qos_policy()` 가 봉투를 손대지 않아 `subscriptionId`/`notifCorrId`/`resourceUri` 와 타임스탬프 29곳이 템플릿 고정값(2026-03-01)으로 나갔다. `build_15f_cell_power()` 와 같은 시그니처로 맞추고 `sub_id`/`corr_id`/`decision_iso` 로 전부 덮어쓰도록 수정. **11:11 실기동 재확인: 잔존 0건, 양쪽 200** | `captured/14_e_control_NCOF_to_PCF_{BEFORE,AFTER}_envelope_fix.json` |
| 높음 | metric 진동 (§5) — 한 구독의 두 UPF 스트림 중 "최신 UDUM" 하나만 골라 쓴다 | `data_analyzer.py:213-227` |
| 중간 | `data_analyzer.py:184-185` 필터가 NEF/UPF 경계는 긋지만 **WLAN/비-WLAN 경계는 긋지 않는다** | 아래 §7 참조 |

### 6.1 `13p_d` 구조적 결함 5종 — 자동 수리 불가

**대상**: `/home/dodo1/SBI/app/templates/send/` 의 `13p_d_…v1.0.tmpl`, `…_POWER.tmpl`, `…_SIGNAL.tmpl` **3개 모두**
**규격 근거**: `generated/nnef/openapi.yaml`(양측 합의 규격), 3GPP TS 29.571 / TS 38.413
**실측**: 2026-09-09~09-10 RICF 통지 **689건** 수신분 (`logs/lenient_ingest/ledger.jsonl`)

| # | JSON 경로 | 현재 값 | 규격 | 건수 |
|---|---|---|---|---|
| 1 | `eventNotifs[].timeStamp` | 키가 **`timestamp`**(소문자 s) | `timeStamp` — **필수**, 대소문자 구분 | 1,378 |
| 2 | `eventNotifs[]._rfSignalInfos[]._nodeAddrs` | **배열** `[{…}]` | `$ref: AddrFqdn` — **단일 객체** | 1,378 |
| 3 | `…_loc.nrLocation.tai` | **키 없음** | `NrLocation.required: [ncgi, tai]` | 1,378 |
| 4 | `…_loc.nrLocation.ncgi` | UE1 에 **키 없음**(UE2 는 있음) | 위와 동일 | 689 |
| 5 | `…_loc.nrLocation.ncgi.nrCellId` | `"cell-002"` | `^[A-Fa-f0-9]{9}$` (36비트 hex 9자리, TS 38.413 §9.3.1.7) | 689 |

건수는 `689건 × (UE 2개 또는 이벤트 2종)` 으로 전부 정합한다. 값 형식 자체는 정상이므로 1번은 **키 이름만** 고치면 된다.

> ⚠️ 2번은 `_` 접두 **확장 필드**다. "복수 노드를 실어야 한다"는 의도라면 배열이 맞고 **우리 규격/모델을 바꾸는 게 옳다.** 어느 쪽이 의도인지 회신을 받아야 한다 — 일방적으로 두두원 결함으로 단정하지 말 것.

**왜 관대 수신이 못 고치는가**: `tai`/`ncgi` 의 TAC·셀 ID 를 지어낼 수 없고, `"cell-002"` 에서 올바른 hex 를 유도할 근거가 없으며, `_nodeAddrs` 는 첫 원소만 취해도 되는지 합의가 필요하다. 키 이름 오타(`timeStamp`)는 오탐 위험 때문에 추측 수리 대상에서 의도적으로 제외했다.

**영향**: `13p_d` 는 **현재 100% 거절**된다. 나머지 통지(`8_`, `9_`, `10_a`, `11p_b`, `12p_c`)는 수리 후 정상 처리된다.

### 6.2 하위 구독 응답의 구독 ID — mockup 과의 결정적 차이

두두원 응답에는 ID 가 **본문에도 헤더에도 없다**. 그래서 `_send_external_subscription` 이 `None` 을 돌려주고,
`subscription_handler.py:328` 의 `if external_sub_id:` 가 레코드를 통째로 버린다 → `external_subscriptions` 가 `[]`
→ GUI 팬아웃 미표시 · 상태 미저장 · **구독 해지 영구 불가**(고아 구독 누적).

| NF | 성공 응답 | ID 위치 |
|---|---|---|
| mock SMF `:9001` (4건) | 201 | 본문 `subId` **+** `Subscription-ID` 헤더 |
| mock AF/RICF `:9002` (6건) | 201 | **`Subscription-ID` 헤더 전용** (본문 주입은 `simulation.py:232` 에 주석 처리) |
| NCOF 자신 `:9000` | 201 | `Subscription-ID` 헤더 |
| **두두원** | **200** | **없음** |

**요청 사항**: uuid4 를 발급해 **`Subscription-ID` 응답 헤더**로 실어 달라 — 본문 구조를 바꾸지 않아도 되는 가장 작은 수정이고,
6종 요청 형태에 모두 통한다. 참조 구현은 `nsmf-server/src/nsmf/impl/subscriptions_collection_api_impl.py:51-52, 73-77`.

> 📌 **주의 — 이건 순수한 두두원 결함이 아니다.** 두두원은 요청 본문의 `notifId` 를 자기 `subscription_id` 로 채택하고
> (`ncof_flow_subscription_handlers.cpp:53-54, 353-354, 446-447, 603-604, 681-682`), DELETE 도 `key‖subscription_id‖notif_id`
> 셋 다 매칭한다(`ncof_flow_subscription_core.cpp:1207`). **즉 NCOF 는 해지에 필요한 값을 이미 스스로 만들어 갖고 있다.**
> 2p 핸들러(`:202`)는 요청의 `subscriptionId` 를 읽는데 **NCOF 는 그걸 보내지 않는다**(`subId` 는 `null` 로만 나감).
> 양측 수정으로 제안할 것. NCOF 측 폴백은 §8 참조.

전체 원장: `logs/lenient_ingest/ledger.jsonl` (샘플은 `captured/lenient_ledger_sample.jsonl`)

---

## 7. ⛔ 이미 반증된 가설 — 다시 파지 말 것

| 가설 | 판정 |
|---|---|
| `PEF_FLOW` 오타가 400 의 원인 | ❌ 두두원 소스에 `granularityOfMeasurement` 참조 자체가 없음. 수정은 규격 준수 차원 |
| 이중 슬래시 `//subscriptions` 가 400 의 원인 | ❌ 이 400 과 무관한 것은 맞다. 단, "경로를 통째로 폐기한다" 는 서술은 부정확 — 5/5p 분기만은 경로를 읽는다(§3 📌) |
| 방화벽/ufw 가 콜백을 막는다 | ❌ `journalctl -k` 에 `10.254.173.46` 발 `DPT=9000` 차단 0건. TCP 연결 실측 성공 |
| HTTP/2 h2c 협상 문제 | ❌ 200 응답이 `HTTP/2` 로 정상 협상됨 |
| 7P 핸들러가 `8p_` 를 보내야 정상 | ❌ 7/7p 는 `12_c`/`12p_c` 만 보냄. `8_` 계열은 kind 3/3p 전용 |
| `exclude_none=True` 가 UPF 리포트를 살린다 | ❌ #6 이 7P→7 로 옮겨갈 뿐 같은 9시간 벽. 별개 이슈로만 가치 있음 |
| 템플릿 파일명 공백이 원인 | ❌ 코드가 참조하는 공백 없는 이름이 실제로 존재 |
| `notifUri` 가 NCOF 에 도달 못 한다 | ❌ 도달함. `10.254.73.47:9000` 으로 연결 실측 확인 |
| NEF 422 를 고치면 결정 루프가 돈다 | ❌ `data_analyzer.py:184-185` 가 `NefEventExposureNotif` 를 배제. UPF `NotificationData` 만 소비 |
| 제어 명령이 두두원 substring 검출기에 안 걸려 400 이 날 것이다 | ❌ 14/15F 분기가 **맨 앞**에 있고 둘 다 최상위 JSON 배열을 명시 지원한다(`ncof_flow_control.cpp:247-262`, `:523-538`). 실측 200 |
| 제어 명령 실패는 400 으로 나타난다 | ❌ 라우팅 후 대상 0건이면 **500** 이다(`ncof_flow_subscription_handlers.cpp:761-784`) |
| `Content-Type` 이나 최상위 `[` vs `{` 가 문제가 될 수 있다 | ❌ 검출은 원문 substring 매칭이라 `[`/`{` 무관. Content-Type 은 저장만 하고 아무 데서도 읽지 않는다 |
| 포트(55555 vs 55556)가 메시지 라우팅에 영향을 준다 | ❌ 네 포트 모두 같은 `Start_Http2_Server` + 단일 디스패처(`main.cpp:277-306`, `http2_server.cpp:369-370`) |
| **RICF 가 다음 주기 통지에 `cell_power_state` 를 에코한다** | ❌ **에코 기능 자체가 없다.** `_powerState` 는 템플릿 하드코딩이고 수신 제어는 DB INSERT 2건 + gNB2 SSH 로 끝난다(§5) |
| 두두원 `send_json/` 을 보면 제어 수신 여부를 알 수 있다 | ❌ `send_json/` 은 **송신 덤프 전용**. 수신 제어는 MySQL 로만 간다 |
| `13p_d` 와 `8_`/`9_`/`10_a` 는 별개 스케줄러로 나간다 | ❌ 단일 `Ncof_Subscription_Report_Thread`(`ncof_flow_subscription_core.cpp:905-984`) 1초 폴링이 전부 처리 |

> §3 의 `Detect_Ncof_Recv_Json_Type()` 인용과 "`(void)path;` 로 경로를 폐기한다" 는 서술은
> **2026-09-10 에 정정됐다**(§3 의 📌 참조). 14/15F 분기 누락과, 5/5p 분기만은 경로를 읽는다는 점.

---

## 8. 다음 할 일

**차단성 블로커는 없다.** 제어 루프는 관통됐고, 남은 것은 통보·검증·정리다.

### ⭐ 가장 먼저 — 두두원에 §6 목록 전달

`notificationURI` 오타는 **해결됐다.** 남은 치명 1건은 **ISO8601 소수 초 파서**(패치 A 가 우회 중)이고,
그 다음이 §6.1 스키마 결함 5종(패치 B 가 우회 중)과 §6.2 하위 구독 ID 결손이다.
근거 데이터는 `logs/lenient_ingest/ledger.jsonl`, 실제 제어 본문은 `captured/1{4_e,5_f}_control_*.json`.

**임시 패치 회수 현황:** A(소수 초) ⏳ · B(관대 수신) ⏳ · C(URI 치환) ✅ 완료

### 남은 검증 1건 — gNB2 가 실제로 꺼졌는가

이번 실측이 보장하는 것은 **두두원이 제어 명령을 파싱·라우팅·기록했다(HTTP 200)** 까지다.
`sshpass … eu.gnbControl.py cell-stop` 이 실제로 성공했는지는 **미확인**이다 —
두두원 stderr 는 파일로 안 남고, gNB2 호스트 접근과 DB 조회가 이번 작업의 읽기 전용 제약에 걸렸다.

확인하려면 둘 중 하나가 필요하다:
1. 두두원 담당자가 `sbi_poc_app` stderr 에서 `gnb_ssh_control` 로그를 확인해 주거나,
2. gNB2 호스트(`root@<gnb2_ip>`)에서 셀 상태를 직접 관측.

### NCOF 측 정리 (우선순위 순)

1. ~~**14_e 제어 본문의 하드코딩 값 수정**~~ — **완료** (`1335888`, 2026-09-10 11:11 실기동 확인).
   `apply_qos_policy()` 가 `build_15f_cell_power()` 와 같은 인자를 받아 봉투 29곳을 덮어쓴다.
   `Gnb2RLEngine` 은 `generate_notification` 을 상속받으므로 자동 적용.
   > 하드코딩된 `subscriptionId` 는 이것 하나뿐이었다. `core/15f_….json` 에도 같은 고정값이 있지만
   > 그 파일은 `test.py:22` 의 **주석 처리된 줄**에서만 언급되는 죽은 파일이고, 라이브 15f 는
   > 코드로 생성된다. 저장소 전체 전수 조사 결과 다른 하드코딩 지점은 없다.
2. **metric 진동 수정** — 한 구독의 두 UPF 스트림 중 최신 하나만 고르는 대신,
   WLAN_PERFORMANCE 스트림을 명시적으로 선택하거나 두 스트림을 합성. (`data_analyzer.py:213-227`)
3. **`data_analyzer.py:184-185` 필터 정교화** — NEF/UPF 경계만 긋고 WLAN/비-WLAN 경계는 안 긋는다.
4. 두두원이 **소수 초 파싱을 고치면** `_DODO1_NO_FRACTIONAL_SECONDS = False`(패치 A) 로 되돌리고 재검증.
5. ~~두두원이 **`notificationURI` 오타를 고치면** 패치 C 를 비우고 재검증~~ — **완료 (2026-09-10 17:30).**
   패치 C 제거 후 파일이 도입 이전 블롭과 동일함까지 확인. 상세는 §4.
6. 연동이 안정화되면 **관대 수신 계층 제거** — `NCOF_LENIENT_INGEST` 를 끄고,
   최종적으로 `core/lenient_ingest.py` 와 `main.py` 의 2줄을 삭제. (패치 B)

### 참고 — 기동 시 주의

- `main.py:88` 의 `restore_persisted_subscriptions()` 는 **주석 처리돼 있다.** 저장 구독을 복원하지 않으므로
  **NCOF 를 재기동하면 두두원도 재기동해야 한다** — 두두원은 `Send_First_PCF_to_NCOF`/
  `Send_First_RICF_to_NCOF`(`main.cpp:199`, `:258`)에서 **기동 시 딱 한 번만** 구독을 보낸다.
- `NCOF_LENIENT_INGEST=1` 를 빠뜨리면 통지가 전부 422 로 거절되고 루프가 돌지 않는다.
  기동 로그 첫머리의 `[LENIENT] 임시 관대 수신 계층 활성화` 배너로 확인할 것.
- 장기 실행 시 fd 누수로 로그가 폭주하므로 `ulimit -n` 을 올려서 띄우는 편이 안전하다.

---

## 9. 참고 자료

- `captured/` — 두두원이 실제로 보낸 본문(`8_`, `9_`, `10_a`, `11p_b`, `13p_d`, 구독 `1_`/`1p_`)과
  NCOF 가 보낸 하위 구독 6건(`payload_1..6.json`). **스키마 대조·회귀 검증에 그대로 쓸 수 있다.**
- `captured/lenient_ledger_sample.jsonl` — 관대 수신 원장 샘플 12건
- `captured/14_e_control_NCOF_to_PCF_BEFORE_envelope_fix.json` — 2026-09-10 09:39:30 에 PCF 로
  보내 200 을 받은 실제 제어 본문. **수정 전** 상태라 템플릿 고정 `subscriptionId`/시각이 그대로 보인다
- `captured/14_e_control_NCOF_to_PCF_AFTER_envelope_fix.json` — 같은 경로, `1335888` 적용 후
  11:11:42 전송분. 라이브 구독 id·현재 시각·`scenario2` 베이스가 반영돼 있다(회귀 비교용 쌍)
- `captured/15_f_control_NCOF_to_RICF_sent_2026-09-10_pretty.json` — 같은 시각 RICF 로 보내 200 을 받은
  실제 제어 본문(`_cellPowerState: DEEP_SLEEP`, `gNBValue: 000002`)

### NCOF 핵심 파일

| 파일 | 역할 |
|---|---|
| `core/subscription_request_builder.py` | 하위 NF 구독 생성. 오늘 수정의 대부분이 여기 |
| `core/subscription_handler.py` | 팬아웃 POST(`:142-181`), 제어 발송(`:223-294`), `_httpx_kwargs`(`:35-42`), TEMP URI 치환(`:46-70`) — **패치 C 로 줄번호가 뒤로 밀렸다** |
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
| `src/http2_server.cpp:369-379` | 단일 디스패처 + 200/400 응답 생성 |
| `src/ncof_flow_control.cpp:138-267` | 14_e(NCOF→PCF) 제어 수신 핸들러 |
| `src/ncof_flow_control.cpp:487-543` | 15F(NCOF→RICF) 셀 전력 제어 수신 핸들러 |
| `src/db.cpp:287`, `:336` | 수신 제어를 `gnb_control_recv`/`gnb_control` 에 INSERT (어디서도 SELECT 안 함) |
| `src/gnb_ssh_control.cpp:109`, `:156-160` | gNB2 로 `eu.gnbControl.py cell-stop` / `cell-start` SSH 셸아웃 |
| `src/main.cpp:199`, `:258` | 기동 시 1회 구독 발송(`Send_First_*_to_NCOF`) |
| `src/main.cpp:277-306` | 네 포트 모두 같은 서버로 기동 |
| `templates/send/13p_d_….tmpl:149`, `:183` | `"_powerState": "ACTIVE"` 하드코딩 (에코 아님) |
