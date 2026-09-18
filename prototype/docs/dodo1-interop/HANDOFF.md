# NCOF ↔ 두두원(DoDoWon) SBI 연동 — 작업 인수인계

**작성:** 2026-09-09 24:00 KST · **갱신:** 2026-09-17 23:36 KST
**작업 브랜치:** `fix/dodo1-timestamp-fractional-seconds` (main 에서 분기, main 대비 **19 커밋 앞섬**. main 은 2026-09-09 21:31 에 `53e8068` 로 ff 된 뒤 그대로여서 분기점이 곧 main 의 끝이다 — 뒤처진 커밋 0)
워크트리 브랜치 `claude/ncof-dodo1-sbi-interop-dc47e5` 는 `b7622f8` 에 멈춰 있다 — **두 브랜치 HEAD 는 더 이상 같지 않다**(본 체크아웃이 `ce71818`·`ba8c7d4` 2 커밋 앞섬). 최신은 본 체크아웃 쪽이다.

```
(HEAD)   docs(dodo1): 9/17 검증 결과 회신 초안 + 수정요청 초안 _nodeAddrs 정정   ba8c7d4
ce71818  fix(sbi): 패치 A 분리 후 회수 — 소수 초 제거만 해제, 시계 오차 마진은 유지
b7622f8  docs(dodo1): 재기동 절차 절 번호를 §8.1 로 정정
3b84b3b  docs(dodo1): HANDOFF 현행화 — 커밋 목록·기동 상태·신규 결함 2건
62170fc  docs(dodo1): 두두원 수정 요청 메일 초안 추가 (4건)
4449cca  docs(dodo1): 재기동 조합별 절차 신설 + "제어 명령 2배" 정정
469b60c  docs(dodo1): 하위 구독 해지 경로 실증 — DELETE 10/10 실장비 200
e49c613  fix(sbi): 고아 하위 구독 해소(notifId 폴백) + 저장 구독 복원 재개
8bc14ea  docs(dodo1): §6.3 규격 원본 감사 반영
2a46b75  fix(sbi): 패치 C 제거 — 두두원이 notificationURI 오타를 고침
81c6689  docs(dodo1): §6.1/§6.2 신설
55b3fcb  docs(dodo1): 14_e 봉투 수정 실기동 검증
1335888  fix(control): 14_e 제어 본문의 템플릿 고정 신원·시각 제거
95f9ed1  docs(dodo1): 제어 루프 관통 확인 및 "RICF 에코" 전제 반증 반영
f614abd  fix(sbi): notificationURI 오타 IP 발송 직전 치환   (패치 C, TEMP → 2a46b75 에서 제거)
4a9c8f0  docs(dodo1): HANDOFF 커밋 상태 갱신
31e7fe2  docs(dodo1): 인수인계 문서와 실측 페이로드 보존
55c589f  feat(diag): 임시 관대 수신 계층 추가            (패치 B — 유일하게 남은 임시 패치)
131cc03  fix(sbi): targetPeriod 마이크로초 제거          (패치 A → ce71818 에서 회수. 60초 백데이트는 분리돼 상시 유지)
53e8068  fix(sbi): 하위 NF 구독 400 해결                (= 현재 main)
e33cb89  (분기 당시 main 이 있던 지점 — main 은 그 뒤 53e8068 까지 전진했다)
```

이 연동 작업과 관련해 커밋되지 않은 것은 셋이다.

| 경로 | 종류 | 처리 |
|---|---|---|
| `prototype/device_info.json` | 수정(추적) | 두두원 IP/포트(55555~55558)를 담은 로컬 환경 설정 — **커밋하지 말 것**. 워크트리 쪽 사본은 localhost mock 포트로 되돌려 놓았다 |
| `prototype/docs/dodo1-interop/두두원_회신_발송본.md` | 신규(미추적) | 9/17 20:36 두두원에 실제로 보낸 회신 본문. 기록 가치가 있으니 **커밋 대상** |
| `prototype/nsmf-server/README.md` | 수정(추적) | 9/17 기동 중 붙여 넣은 메모 7줄(`ncof_state.json` 백업 + `MODE=DEVICE` 기동). 명령 내용은 `nncof-server` 용인데 엉뚱한 파일에 들어갔다 — **`git checkout -- prototype/nsmf-server/README.md` 로 되돌릴 것**(기동 절차는 §8.1 에 이미 있다) |

저장소 루트의 `status.md`·각종 `.pptx`/`.pdf` 등 다른 미추적 파일은 이 연동과 무관하다.

**상태: 제어 루프 관통 + 고아 하위 구독 해소 + 두두원 9/17 수정 3건(소수 초·`13p_d` 구조·단위 접미사) 반영 확인까지 완료**
(단위 접미사는 `12p_c` 경로에서만 실증됐다 — 8p 주기보고 경로는 스루풋 8필드가 100% `-999` 라 값 자체가 없다).
`ce71818` 로 **패치 A 는 회수했다** — `_DODO1_NO_FRACTIONAL_SECONDS = False`. 60초 백데이트는 소수 초와 무관한
시계 오차 마진이라 `if` 밖으로 빼 **무조건 유지**한다. 남은 임시 패치는 **B(관대 수신) 하나뿐**이고
**차단성 블로커는 없다.**

패치 B 는 아직 회수할 수 없다 — 지금 `NCOF_LENIENT_INGEST` 를 끄면 수신 통지의 **70.1%(2,384/3,403)가 422** 다.
원인은 ① `-999` 센티넬(영향 2,384건 = 100%) ② 정수 필드 소수값(1,363건 = 40.1%) 둘뿐이고 **동시에 고쳐야 한다** —
①만 고치면 `-999` 에 가려져 있던 AF PERF_DATA 682건이 ②로 드러나 영향이 **최대 2,045건**까지 는다.

두두원 발송 문서는 초안·발송본이 모두 남아 있다 — 1차는 `두두원_수정요청_메일초안.md`(4건, `62170fc`.
두두원이 9/17 빌드로 1·2·3 을 반영했으니 발송·응답까지 끝났다), 9/17 검증 회신은
`두두원_검증결과_회신초안.md`(내부 검토용 포함)와 발송분만 추린 `두두원_회신_발송본.md`(**아직 미커밋**)다. §8 참조.

### 지금 떠 있는 것 (2026-09-17 20:56 기준) — **양끝 모두 정지 상태다**

| 구성요소 | 상태 |
|---|---|
| NCOF | ⛔ **정지.** 본 체크아웃(`/home/labry/git/ncof_generated/prototype/nncof-server`)에서 커밋된 코드(`ba8c7d4`)로 **20:24:47 기동**(`logs/app.log` 의 `Running on http://0.0.0.0:9000`)했으나 **20:52:07 로그를 마지막으로 멎었다** — 20:56 현재 `:9000` 리스너 없음, hypercorn/`main.py` 프로세스 없음, `/api/*` 응답 없음. 20:46:53 에 `data/ncof_state.json` 이 `ncof_state.json.bak-204653` 으로 치워져 **상태 파일이 없다**(그대로 재기동하면 구독 복원 없이 빈 상태로 뜬다 — §8.1). 기동 당시 환경은 `MODE=DEVICE`, `NCOF_LENIENT_INGEST=1`, `Max open files 65536`(20:50 `/proc/<pid>/limits` 실측) |
| 두두원 | ⛔ **정지.** 바이너리는 9/17 **10:02 재빌드본**(`~/SBI/app/sbi_poc_app` mtime 10:02). 그날 오전 3회 재기동(10:02:57 / 10:05:01 / 10:20:18) → 15:23:01 정지 → 20:27 재기동 → **20:45:05 마지막 송신을 끝으로 다시 정지**(`send_json/*.json` mtime 20:45:05, `pgrep -f sbi_poc` 무응답). 요청했던 `tee ~/SBI/app/sbi_poc_app.<날짜>.log` 기동은 **아직 적용되지 않았다**(`~/SBI/app/` 에 `*.log` 없음) — 정지 원인 규명이 계속 불가하다 |
| 루프 (20:24 런 기준) | 상향 구독 2건 · `external_subscriptions` 10건(PCF 구독 4 + RICF 구독 6) · GUI 간선 18건 · 제어 PCF/RICF 발송 각 1건 **200, 실패 0**(20:28:58 PCF, 20:29:06 RICF). 이 값은 20:24 "청소 후 재기동" 으로 **복구된** 것이다 — 그 직전 오전에는 두두원 3회 재기동으로 구독이 매번 재전송돼 **상향 8 / external 40 / 간선 72** 까지 **4배 중복이 실제로 발생**했다(§8.1 우려의 실증). 8·40 은 `data/ncof_state.json.bak-20260917-202439`, 2·10 은 `…bak-204653` 에서 확인했고, **72 는 18×4 로 추정한 값이다**(서버가 내려가 `/api/subscriptions/relations` 로 직접 재지 못했다) |
| 20:24 런 품질 | 응답 **422 0건 · ERROR 0건.** 단 **이건 패치 B(관대 수신)가 켜져 있어서 나온 수치다** — 같은 구간에 `[LENIENT]` 로그가 2,567줄 쌓였고 위반 유형은 `value_error` 102회 · `greater_than_equal` 85회 · `int_type` 68회다. 수신 통지 총계는 **20:28:55~20:45:05 구간 UPF 68건 · RICF 51건 · AF 51건**(분당 약 4.2 / 3.1 / 3.1건) |
| 브라우저 접근 | 데스크톱에서 `ssh -p 2020 -N -L 9000:127.0.0.1:9000 localhost` → `http://localhost:9000/`. 역터널(`ssh -N -R 2020:localhost:2222 labry@labry.ddns.net`, pid 2787067/2787068)은 이 서버에서 살아 있으나 **NCOF 가 내려가 있어 지금 포워딩해도 열리지 않는다** |

> 워크트리(`.claude/worktrees/ncof-dodo1-sbi-interop-dc47e5`)에도 `uv sync --frozen` 으로 채운
> venv 가 있다. 다만 ① 브랜치가 `b7622f8` 에 멈춰 있어 **패치 A 회수(`ce71818`) 이전 코드**이고
> (`subscription_request_builder.py:74` 의 `_DODO1_NO_FRACTIONAL_SECONDS` 가 아직 `True` — 본
> 체크아웃은 `:89` 에서 `False`), ② 그 안의 `prototype/device_info.json` 은 **localhost mock 포트**로
> 되돌려 놓았다. 즉 워크트리에서 `MODE=DEVICE` 로 띄우면 두두원이 아니라 mock 을, 그것도 소수 초를
> 깎아내는 구버전 코드로 때린다. **실기동은 반드시 본 체크아웃에서 할 것**(§8 「참고 — 기동 시 주의」).

---

## 1. 한 줄 요약

MODE=DEVICE 로 두두원 장비와 붙였을 때 "PCF/RICF → NCOF 구독 이후 아무 진전이 없던" 문제를
NCOF 측 수정 4건(패치 A·B·C + 구독 400 수정)으로 해결했다. 제어 루프 전 구간이 관통되며,
NCOF 가 보낸 `_cellPowerState: DEEP_SLEEP` 제어 명령을 두두원이 200 으로 수락한다.

**2026-09-17 갱신.** 두두원이 10:02 재빌드로 우리 수정 요청 3건(ISO8601 소수 초 · `13p_d` 구조 결함 ·
스루풋 단위 접미사)을 모두 반영했다 — `13p_d` 는 341건 수신에 **잔존 위반 0건**(이전엔 940건 전량 422).
NCOF 는 `ce71818` 로 **패치 A 를 회수**했고(소수 초 제거만 해제, 60초 백데이트는 시계 오차 마진으로
분리해 무조건 적용), 패치 C 는 앞서 `2a46b75` 로 제거했다. **남은 임시 조치는 패치 B(관대 수신) 하나뿐**이며,
이건 두두원의 `-999` 센티넬과 정수 필드 소수값이 **동시에** 고쳐져야 걷어낼 수 있다(§6 참조).

다만 **"RICF 가 cell_power_state 를 에코한다" 는 전제는 사실이 아니었다** — 두두원에는 에코 기능이
아예 없다(§5 참조). 제어 명령의 실제 종착지는 리포트 필드가 아니라 **물리 장비**이고, 9/17 시점에
그게 **둘**이다 — 15F(RICF 향)는 gNB2 의 cell-stop/cell-start 로 나가고, 14_e(PCF 향)는 9/15 신설된
`upf_qos_udp.{h,cpp}` 를 타고 **실장비 UPF 로 바이너리 UDP 를 직접 발사한다**
(`ncof_flow_control.cpp:332-336` `Send_Qos_Apply_To_Upf_Udp(config.upf_ip, config.upf_port, packet)`,
UE 4개(`QOS_APPLY_UE_COUNT`)가 다 차야 발사). **두 경로 모두 NCOF 의 가시성은 0 이다 — HTTP 200 은
여전히 제어 성공을 뜻하지 않는다.**

---

## 2. 환경

| 구성요소 | 위치 |
|---|---|
| NCOF | `10.254.73.47` — `/home/labry/git/ncof_generated/prototype/nncof-server`, hypercorn h2c :9000 |
| 두두원 sbi_poc_app | `10.254.173.46` — `ssh dodo1` (= `dodo1@10.254.173.46 -p 2299`), `/home/dodo1/SBI/app` |
| NF 주소표 | `prototype/device_info.json` — SMF=55557, AF=55558, RICF=55556, PCF=55555 |

두두원 앱은 **소스가 읽을 수 있다**: `/home/dodo1/SBI/app/{src,include,config,templates,send_json}`.
`send_json/` 에는 두두원이 **송신 직전에 남기는 디버그 덤프**가 쌓이므로, "두두원이 실제로 무엇을
`send_json/` 에는 두두원이 **송신 직전에 남기는 디버그 덤프**가 쌓이므로, "두두원이 실제로 무엇을
보냈는가" 를 확인하는 가장 빠른 방법이다.

> ⚠️ 두두원 장비는 **읽기 전용**으로만 다룰 것. 앱 재시작·요청 주입·DB 접근 금지.
> 허용 명령은 `cat` · `sed -n` · `grep` · `ls` · `head` · `find` · `pgrep` · `stat` 까지다.

### 산출물·문서 위치

| 무엇 | 경로 |
|---|---|
| 인수인계(본 문서) | `prototype/docs/dodo1-interop/HANDOFF.md` |
| 1차 수정 요청 메일 초안(4건) | `prototype/docs/dodo1-interop/두두원_수정요청_메일초안.md` (커밋 `62170fc`) |
| 9/17 검증 결과 회신 초안 | `prototype/docs/dodo1-interop/두두원_검증결과_회신초안.md` (커밋 `ba8c7d4`) |
| 두두원에 실제로 보낸 회신 | `prototype/docs/dodo1-interop/두두원_회신_발송본.md` — **미커밋** |
| 실측 페이로드 보존본 | `prototype/docs/dodo1-interop/captured/` — 파일별 설명은 §9 |
| 관대 수신 원장 (현행) | `prototype/nncof-server/logs/lenient_ingest/ledger.jsonl` — 9/17 20:24 이후분만 |
| 관대 수신 원장 (20:24 이전 전체) | 같은 디렉터리 `ledger.jsonl.upto-20260917-202439` — 77,904행 / 487 MB |
| 수리 전 원문 덤프 | 같은 디렉터리 `*.raw.json` — 78,023개 (9/17 20:45 기준) |
| NCOF 앱 로그 | `prototype/nncof-server/logs/app.log` (일자별 `app.log.YYYY-MM-DD` 로테이트) |

> 🔴 **§6.1·§6.3 이 "전체 원장" 이라 부르는 것은 회전본 쪽이다.** 9/17 20:24 청소 때 `ledger.jsonl` 을
> 잘라냈으므로 현행 파일에는 그 이후분밖에 없다(확인 시점 119행). §6.1 의 689건, 패치 B 의 3,403/2,384건
> 같은 과거 수치를 재현하려면 반드시 `ledger.jsonl.upto-20260917-202439` 를 볼 것.

> ⚠️ **"원장에 없다" 는 "안 왔다" 가 아니다.** 관대 계층은 위반이 0 인 통지를 원장에도 `raw.json` 에도
> 남기지 않고 조기 반환한다 — `core/lenient_ingest.py:358-359` 의
> `if report["before_error_count"] == 0: return await self.app(scope, replay, send)` 가 `_log_report`/`_persist`
> (`:361-362`) 보다 앞에 있다. 9/17 재기동(20:27) 뒤 RICF 향 raw 덤프 34건이 전부 10_a PERF_DATA 이고
> **13p_d 는 0건**인 것은 수신이 끊긴 게 아니라 **341건 전수 통과**했다는 증거였다.
> 수신 여부는 원장이 아니라 `app.log` 로 볼 것.

### 기동

```bash
# NCOF (관대 수신 진단 계층 포함)
cd /home/labry/git/ncof_generated/prototype/nncof-server && NCOF_LENIENT_INGEST=1 sh run_http2.sh

# 두두원 (사용자가 직접) — 반드시 로그를 남기고 띄울 것 (9/17 회신으로 요청함, 20:54 현재 미적용)
ssh dodo1 -> cd /home/dodo1/SBI/app && ./sbi_poc_app 2>&1 | tee ~/SBI/app/sbi_poc_app.$(date +%F_%H%M).log
```

`MODE=DEVICE` 는 셸에 export 되어 있어야 한다. `NCOF_LENIENT_INGEST` 를 빼면 관대 수신이 완전히
비활성화된다(미들웨어가 아예 설치되지 않음).

---

## 3. 두두원 장비의 결정적 특성 — 이걸 모르면 전부 헤맨다

**두두원은 JSON 스키마 검증을 하지 않는다. 본문 substring 매칭으로 메시지 종류를 판별한다.**
`/home/dodo1/SBI/app/src/ncof_flow_common.cpp` 의 `Detect_Ncof_Recv_Json_Type()`
(**2026-09-15 04:20 재빌드본 기준 `:421~:518`** — 9/10 판이 적은 `:391~:488` 에서 통째로 +30 행 밀렸다):

```c
NcofRecvJsonType Detect_Ncof_Recv_Json_Type(const std::string& path, const std::string& body) {
    (void)path;                        // :423 — 있긴 하다. 그런데 :504 에서 path 를 다시 읽는다.
    // ⚠️ 아래 두 분기가 가장 먼저 온다 — NCOF→두두원 "제어 명령" 이 여기로 갈린다 (:425~:434)
    if (has("eventNotifications") && has("QOS_POLICY_ASSIST")
                                  && has("qosPolAssistInfos"))            return 14  (NCOF→PCF);
    if (has("eventNotifications") && (has("_CELL_POWER_CTRL")
                                  ||  has("_cellPowerCtrlOptInfos")
                                  ||  has("_cellPowerParamSet")
                                  ||  has("_cellPowerState")))            return 15F (NCOF→RICF);
    // ↓ 이하가 두두원→NCOF 구독 계열
    if (has("eventsSubs") && (has("_POWER_ENERGY_CONSUMPTION") || has("_RF_SIGNAL"))) return 2P;  // :436~:439
    if (has("serviveName") && has("nsmf-event-exposure"))                  return 3계열;          // :441~:486
    if (has("eventsSubs") && has("DISPERSION"))                            return 6P;             // :488~:491
    if (has("eventsSubs") && has("PERF_DATA") && has("dap-001"))                                  // :493~:500
        return has("n3IwfId") ? 4 : 4P;                                   // :495~:499
    if (has("eventsSubs") && has("PERF_DATA") && has("dap-002"))                                  // :502~:509
        return (Text_Has(path,"5p") || Text_Has(path,"10p")) ? 5P : 5;    // :504 ← 유일한 path 참조
    // ⚠️ 봉투(eventNotifications) 없이도 15F 로 잡는 fallback — UNKNOWN 바로 앞 (:511~:515)
    if (has("_CELL_POWER_CTRL") || has("_cellPowerParamSet")
     || has("_cellPowerState")  || has("_cellTxPower"))                    return 15F;
    return NCOF_RECV_UNKNOWN;                     // :517 → 핸들러가 400 반환
}
```

> 📌 **2026-09-10 정정.** 이 문서의 이전 판은 위 두 분기를 누락하고 `(void)path;` 로 시작한다고 적었다.
> 실제로는 (a) **14/15F 제어 분기가 맨 앞에 온다**, (b) 경로를 통째로 버리지는 않는다 —
> **5/5p 를 가르는 한 분기만은 `path` 를 읽는다.** 나머지 분기에 대해서는 경로 무관이 맞다.

> 📌 **2026-09-17 재정정 — 위 박스의 표현이 오해를 낳는다.** 이전 판이 적은 `(void)path;` 는
> **:423 에 실제로 있다**(미사용 경고 억제용 no-op). 즉 이전 판에서 틀렸던 것은 `(void)path;` 라는
> 서술이 아니라 **"그래서 경로를 통째로 버린다" 는 결론 하나뿐**이다. `(void)path;` 가 있어도
> :504 한 분기만은 `path` 를 읽는다.

> 📌 **2026-09-17 보강 — 이전 판의 `...` 에 가려져 있던 두 가지.**
> (a) dap-001 분기는 "4계열" 로 뭉뚱그릴 게 아니라 `n3IwfId` 유무로 **4 / 4P 를 다시 가른다**(:495~:499).
> (b) UNKNOWN 직전에 **봉투 없는 15F fallback** 이 있다(:511~:515). `eventNotifications` 봉투가 없어도
> `_CELL_POWER_CTRL`/`_cellPowerParamSet`/`_cellPowerState`/`_cellTxPower` 중 하나만 있으면 15F 핸들러로
> 들어간다. **봉투 형식을 바꿔 실험할 때 400 이 안 나고 조용히 15F 가 탄다 — 400 이 안 왔다는 사실만으로
> 봉투가 맞았다고 판단하면 안 된다.**
> 이 fallback 이 9/15 재빌드에서 새로 생겼다는 근거는 없다. 함수 길이가 9/10 판과 같은 98행이고
> 시작·끝이 정확히 +30 행 이동했을 뿐이므로(같은 파일의 `Is_7p_Nsmf_Event_Exposure` 도 :200~:218 → :230~:248),
> **이전부터 있었으나 이 문서의 코드 블록에서 `...` 로 생략돼 있었다고 보는 것이 타당하다.**
> dodo1 에 구버전 소스·형상관리·백업이 없어 신설 여부는 최종 확인 불가.

---
※ **동반 수정(§3 코드 블록 밖. 같은 파일을 가리키므로 안 고치면 문서 내부가 어긋난다)**

- **132행** — `3 / 3P / 7 / 7P 를 가른다(:416~:455, Is_7p_Nsmf_Event_Exposure :200~:218).`
  → `3 / 3P / 7 / 7P 를 가른다(:441~:486, Is_7p_Nsmf_Event_Exposure :230~:248).`
- **768행** — `| src/ncof_flow_common.cpp:391-488 | 메시지 종류 판별(substring 매칭) |`
  → `| src/ncof_flow_common.cpp:421-518 | 메시지 종류 판별(substring 매칭) |`
- **769행**(참고, 미검증) — `src/ncof_flow_subscription_core.cpp:208-259 | ISO8601 파서 (소수 초 버그)`.
  이 파일도 9/15 04:20 재빌드본이고 요청 1 이 해소됐으므로 줄 범위·"(소수 초 버그)" 설명 모두
  담당 절에서 재확인 필요.

- **경로(이중 슬래시 `//subscriptions` 포함)는 400 과 무관하다.**
- **포트는 라우팅에 전혀 영향이 없다.** `main.cpp:277-306` 이 55555/55556/55557/55558 네 포트를
  모두 같은 `Start_Http2_Server` 로 띄우고, 전부 `http2_server.cpp:369-370` 의 단일 디스패처를 탄다.
- **제어 명령의 실패 응답은 400 이 아니라 500 이다.** 본문이 14/15F 로 라우팅됐지만 대상이 0건이면
  핸들러가 0 을 반환하고 `ncof_flow_subscription_handlers.cpp:761-784` 가 500 을 준다.
  NCOF 는 200/204 외 전부를 실패로 처리하므로(`subscription_handler.py:248`) 로그에 `제어명령 실패`
  로 남는다. **즉 제어 명령을 디버깅할 때 500 은 "라우팅은 됐다" 는 신호다.**
- 두두원에는 **14_e / 15f 수신용 템플릿이 없다**. `templates/` 아래에는 `send/` 19개(전부 송신용)뿐이고,
  수신 제어는 필드 단위로 직접 파싱한다. NCOF 가 맞춰야 할 템플릿 계약은 존재하지 않는다.
- 3 계열 내부 분기는 **2026-09-15 빌드에서 이벤트 타입 토큰 기준으로 다시 짜였다**
  (`ncof_flow_common.cpp:441~:486`, 함수 전체는 `Detect_Ncof_Recv_Json_Type()` `:421~:518`).
  `"serviveName"` + `"nsmf-event-exposure"` 로 3 계열에 들어온 뒤 순서대로 —
  1. `"UPF_EVENT"` + `"QOS_MONITORING"`(:455) → `"n3IwfId"` 가 **없으면 3P, 있으면 3**
  2. `"UPF_EVENT"` + `"USER_DATA_USAGE_MEASURES"`(:465) → 먼저 `Is_7p_Nsmf_Event_Exposure()`(:230~:248,
     `"subId"`·`"altNotifFqdns"`·`"altNotifIpv4Addrs"` 중 **하나라도 있으면 7P**),
     아니면 `"gNbId"`|`"gNBValue"`(:452) 가 있을 때 `"n3IwfId"` 유무로 3P/3, 그것도 없으면 **7**(:482)
  3. 둘 다 아니면 **3**(:485)

  두 이벤트 타입이 한 본문에 다 들어 있으면 **1번이 먼저 잡혀 `USER_DATA_USAGE_MEASURES` 는 판정에 관여하지 못한다.**

- **판정 축이 "키 4개" 에서 "이벤트 타입 + 키" 로 바뀌었을 뿐, 여전히 키의 존재 여부만 본다.**
  `Text_Has()`(:212) 는 원문 substring 검색이라 **값이 null 이어도 "있다" 로 센다.** NCOF 는
  `subscription_handler.py:131` 에서 `jsonable_encoder(req_body)` 를 `exclude_none` 없이 호출하고,
  현재 모델은 `NsmfEventExposure` 가 **항상** `subId`/`altNotifIpv4Addrs`/`altNotifFqdns` 를,
  `GlobalRanNodeId` 가 **항상** `n3IwfId`/`gNbId` 를 null 로 싣는다. 그래서 오염은 "가끔" 이 아니라 **결정론적**이다 —

  | 우리 본문 | 실려 나가는 null 키 | 두두원 판정 | `exclude_none=True` 였다면 |
  |---|---|---|---|
  | QOS_MONITORING + UDUM (`captured/payload_2.json`) | `"n3IwfId": null` (:37, :53) | **3** (3P 안 됨) | 3P |
  | UDUM 단독 · RICF WLAN (`captured/payload_6.json`) | `"subId": null`(:14)·`"altNotifIpv4Addrs": null`(:17)·`"altNotifFqdns": null`(:19)·`"gNbId": null`(:38) | **7P 고정** | 7 |

  즉 `networkArea`(ranNodeId)가 실리면 1번 분기는 **항상 3**, 2번 분기는 `subId: null` 때문에 **항상 7P** 다.
  §7 의 기각 가설 표(`exclude_none=True` → #6 이 7P→7)와 같은 현상이며, 9/15 재작성 뒤에도 결론은 동일하다.
  (`payload_2`/`payload_6` 는 `53e8068` 이전 캡처라 `serviveName` 값이 밑줄판이지만, null 키 구조는 지금도 그대로다.)

  > 📌 **2026-09-17 정정.** 이전 판의 `:416~:455` / `Is_7p_Nsmf_Event_Exposure :200~:218` 은
  > **9/15 이전 빌드의 줄 번호**이며, 판정이 `"gNbId"`/`"n3IwfId"`/`"subId"`/`"altNotifFqdns"` **4개 키만으로**
  > 이뤄진다는 서술도 그 시점 기준이다. 새 빌드에서는 1차 관문이 이벤트 타입 토큰이고,
  > `"altNotifIpv4Addrs"` 가 **7P 트리거로 새로 추가**됐으며 `"gNBValue"` 가 `"gNbId"` 의 대체 키로 인정된다.
- **UPF 사용량 리포트(`8_` 계열)는 오직 kind 3/3p 에서만 나온다.** 7/7p 는 `12_c`/`12p_c` 를 보낸다.
- 400 응답 본문은 언제나 `{"error":"bad request"}` 고정 — 이유를 알려주지 않는다.
  실제 사유는 stderr(`log_message`)에만 남고 파일로 저장되지 않는다.
- 구독 성공 시 **200** 을 주고 본문은 `{"result":"ok"}` 뿐. `subscriptionId`/`subId`/`Location`/
  `Subscription-ID` 를 **전혀 주지 않는다**(`http2_server.cpp:372-375`).
- 🆕 **14_e 를 받으면 두두원이 실장비 UPF 로 바이너리 UDP 를 직접 쏜다 (2026-09-15 신설, 사전 통보 없음).**
  `ncof_flow_control.cpp:332-341` 이 `Send_Qos_Apply_To_Upf_Udp(config.upf_ip, config.upf_port, packet)`(`:334`)
  을 호출한다. 페이로드는 JSON 이 아니라 **구조체 그대로의 바이너리**다 —
  `{double gbr_dl; double mbr_dl; char imsi[16];}` × `QOS_APPLY_UE_COUNT`(4) = **고정 128 바이트**
  (`include/upf_qos_udp.h`). `sendto()` 한 방이고 재전송도 응답 확인도 없다(`src/upf_qos_udp.cpp`).
- **발사 조건은 `udp_fill_count == QOS_APPLY_UE_COUNT` — 정확히 4다**(`:332`). 슬롯 번호는
  `qosPolAssistSets` 의 **배열 순번**이라 5번째 이후 set 은 `14_e invalid UE index` 로 버려진다(`:138-142`).
  한 set 이 슬롯을 채우려면 ⓐ `qosParamSet.gbrDl`·`mbrDl` 이 비어 있지 않고(`:79-83`)
  ⓑ `spatialValidity.gRanNodeIds` 가 배열이며(`:98-103`) ⓒ 그중 최소 1건이 DB 저장에 성공해야 한다(`:133-136`).
  **하나라도 모자라면 `QOS UDP not sent fill count=…` 로그만 남고 아무것도 나가지 않는다.**
  우리 현행 14_e 는 `qosPolAssistSets` 4개를 모두 채워 보내므로 조건 자체는 만족한다.
- ⚠️ **UDP 에 실리는 IMSI 는 우리가 준 값이 아니다.** 두두원이 자기 MySQL 에서 읽는다 —
  `Load_Ncof_Target_Item_Supi_Local()`(`ncof_flow_report_db.cpp:180`, 쿼리 `:201-206`)이
  `ncof_sub_target` 에서 `profile_id`=설정 프로필 · `event_idx=0` · `item_idx` 0~3 의 `tgtue_supi` 4건을
  꺼내 `imsi-` 접두를 떼고 쓴다(`ncof_flow_control.cpp:195`, `:150-152`). **14_e 본문의 SUPI 는 무시된다.**
  로드가 실패해도 로그만 남기고 진행하며(`:195-198`) 벡터는 항상 `resize(4)`(`report_db.cpp:190`)라
  `:144-148` 의 크기 검사는 걸리지 않고 **빈 IMSI 가 그대로 실린다.**
  즉 우리가 정할 수 있는 것은 **슬롯 수와 GBR/MBR 값뿐이고, 대상 UE 는 두두원이 정한다.**
- ⚠️ **단위가 조용히 소실된다.** 우리는 `gbrDl`/`mbrDl` 을 `"5.0 Mbps"` 같은 **단위 붙은 문자열**로 보내는데
  (`decide_wlan_gnb2_rule.py:404-405`), 두두원은 `std::stod()` 로 앞쪽 숫자만 읽는다(`:87-88`).
  `std::stod` 는 후행 문자에 예외를 던지지 않으므로 **에러 없이 `5.0` 이 UDP 에 실린다.**
  UPF 가 이 값을 bps 로 해석하면 10⁶ 배 오차다. 두두원의 "단위 접미사" 수정(§6 요청 3)은
  두두원 **송신** 토큰표 건이라 이 경로와 무관하다 — **우리 쪽 숫자 표현도 따로 확인해야 한다.**
- **UDP 성공·실패는 SBI 응답을 바꾸지 못한다.** 핸들러는 UDP 결과가 아니라 `set_count` 를 반환하고(`:351`),
  전송 실패는 `log_message` 로만 남는다. 위의 500 규칙은 그대로다 —
  **`set_count` 가 0 이면 500, 1 이상이면 UDP 가 실패해도 200.**
  게다가 9/17 20:27 재기동본은 stdout 을 파일로 남기지 않아(`~/SBI/app/*.log` 0건)
  **두두원 서버에서조차 발사 여부를 사후 확인할 수 없다.**
- 대상 주소는 두두원 설정 파일 값이다 — `config/6g.config` 의 `UPF_IP=192.168.1.182`, `UPF_PORT=5555`
  (`config.cpp:90`, `:94`). **NCOF 가 지정할 수 없고, 비어 있지 않으므로 발사 조건은 이미 갖춰져 있다**
  (`upf_qos_udp.cpp` 는 ip 가 비었거나 port≤0 일 때만 `invalid UPF UDP target` 으로 되돌아온다).
- 9/17 회신(`두두원_회신_발송본.md` §3-①)에서 ① 이 경로가 지금 활성인지 ② 실패를 NCOF 가 알 방법이
  있는지(없으면 실패 시 500 을 달라) ③ 미달 시 우리가 보내야 할 최소 UE 수를 물어 둔 상태다.
  **답신 전까지 "제어가 UPF 에 반영됐다" 고 쓰지 마라 — 우리는 이 구간을 전혀 관측할 수 없다**(§8 「남은 검증」 참조).
  `include/upf_qos_udp.h`(9/15 04:20) + `src/upf_qos_udp.cpp`(9/15 22:57). 9/17 10:02 재빌드된
  바이너리에 들어 있다. 경로는 `ncof_flow_control.cpp` 의
  `Handle_Recv_14e_Qos_Policy_Assist()`(:178-352) → 세트마다
  `Handle_Recv_14e_Qos_Assist_Set()`(:37-168) 이 `packet.ue[ue_index]` 를 채우고(:157-160),
  `udp_fill_count == QOS_APPLY_UE_COUNT`(=4) 일 때 `:332-341` 의
  `Send_Qos_Apply_To_Upf_Udp(config.upf_ip, config.upf_port, packet)` 이 발사된다.
  - **대상 `UPF_IP=192.168.1.182` / `UPF_PORT=5555`(`config/6g.config`) 는 두두원 호스트 자신의
    5G 코어측 NIC 다** — `enp131s0f0 = 192.168.1.182`, `enp131s0f1 = 10.254.173.46`(우리가 ssh 하는 쪽).
    별도의 "실장비 UPF 박스" 가 아니다. **조사 시점에 UDP/5555 에 리스너가 없었다**
    (`ss -lun` 에 PFCP 8805/8806 만 존재). UDP `sendto()` 는 수신자가 없어도 성공하므로
    `upf_qos_udp.cpp:43-47` 판정은 늘 통과하고 `:50` 이 `QOS UDP send Success` 를 찍는다 —
    **아무도 안 받아도 성공 로그가 남는다.**
  - 페이로드는 JSON 이 아니라 C 구조체 `QosApplyUdpPacket`
    (`{ double gbr_dl; double mbr_dl; char imsi[16]; } × 4` = **128바이트 고정**, 패딩 없음) 을
    **호스트 바이트오더 그대로** `sendto()`(`upf_qos_udp.cpp:39`) 한 것이다.
  - **IMSI 는 NCOF 페이로드에서 오지 않는다.** `Load_Ncof_Target_Item_Supi_Local()`
    (`ncof_flow_report_db.cpp:180-206`) 이 두두원 DB `ncof_sub_target` 에서
    `profile_id='DEFAULT'`·`event_idx=0`·`item_idx 0..3` 4행을 읽어 오고(`imsi-` 접두사 제거),
    NCOF 가 보낸 `qosPolAssistSets` 의 **순번(`ue_index`)** 으로만 매칭한다.
    즉 **NCOF 는 어느 UE 에 정책이 꽂히는지 알 수 없다.**
    ⚠️ 로더가 `target_supis.resize(4)` 를 **먼저** 하고(:190) 실패해도 로그만 찍고 진행하므로
    (`ncof_flow_control.cpp:195-198`), DB 조회가 실패하면 **빈 IMSI 4개로 그대로 발사된다** —
    빈 값 검사가 없다. `ue_index >= target_supis.size()` 분기(:144-148)는 크기가 항상 4 라 죽은 코드다.
  - **발사 조건은 "세트 4건" 이 아니라 "성공한 세트 정확히 4개" 다.** 세트가 `true` 를 주려면
    ① `gbrDl`/`mbrDl` 이 비어있지 않고(:79-83), ② `std::stod` 파싱 성공(:87-93),
    ③ `spatialValidity.gRanNodeIds` 가 배열(:99-102), ④ `Save_14e_Ncof_To_Pcf_By_Config()` 로
    **DB 저장이 1건 이상 성공**(:124-136) 해야 한다. **MySQL 이 죽으면 세트가 4건이어도 UDP 는 안 나간다.**
  - NCOF 의 현재 14_e 는 `qosPolAssistSets` 를 4건 싣는다
    (`core/14_e_NncofEventsSubscriptionNotification_from NCOF_to_PCF_v1.0.json`,
    `captured/14_e_control_NCOF_to_PCF_{BEFORE,AFTER}_envelope_fix.json` 모두 실측 4건).
    ⚠️ **세트를 4개 미만으로 줄이면 UDP 가 조용히 안 나간다** — 두두원 stderr 에
    `QOS UDP not sent fill count=N required=4`(:345-346) 만 남고 NCOF 는 여전히 200 을 받는다.
    반대로 **4개를 넘기면 앞 4개만 실려 그대로 발사된다** — `qos_set_index` 는 성공 여부와 무관하게
    증가하고(:305) 5번째부터는 `:138-142` 에서 `false` 를 받아 `udp_fill_count` 가 4 에 머물기 때문이다.
    (단 5번째 이후 세트도 DB 저장은 그대로 된다 — 인덱스 검사가 저장 루프 **뒤**에 있다.)
  - ⚠️ `gbrDl`/`mbrDl` 은 `std::stod()` 로 파싱돼 **단위 접미사가 버려진다**(`"5.0 Mbps"` → `5.0`).
    NCOF 가 단위를 Mbps→bps 로 바꾸면 UPF 쪽에 10⁶배 값이 그대로 꽂힌다. (§6.2 의 `bps` 명시 요구와 충돌)
  - **NCOF 에 이 경로의 가시성은 0 이다.** 단, 15F 의 gNB2 SSH 와 **순서 구조가 다르다** — 15F 는
    `save_count` 가 SSH 셸아웃보다 **앞서** 확정되지만(§5), 14_e 는 UDP 발사(:332-341) 가 먼저 일어나고
    그 **뒤에** `return set_count`(:351) 가 응답을 가른다(`ncof_flow_subscription_handlers.cpp:765-771`).
    결과는 같다 — **UDP 성패는 응답 코드에 전혀 반영되지 않는다.** 200 은 `set_count > 0` 만 뜻한다.

---

## 4. 적용한 NCOF 측 수정 (2026-09-09 ~ 09-17)

> 아래 4개 커밋의 상세가 이 절에 있다. 같은 기간의 다른 NCOF 수정 — `1335888`(14_e 봉투 고정값)과
> `e49c613`(고아 하위 구독) — 은 §6 · §8 에 있다.

| 패치 | 커밋 | 내용 | 상태 |
|---|---|---|---|
| — | `53e8068` | 하위 NF 구독 400 해결 | ✅ 영구 반영 |
| **A** | `131cc03` → `ce71818` | TEMP `_DODO1_NO_FRACTIONAL_SECONDS` — ISO8601 소수 초 제거. UPF 주기 리포트 미수신(`start_epoch` 이 +9시간 미래로 예약되던 것) 해결 | ✅ **2026-09-17 분리 후 회수.** 두두원이 파서를 고쳐 소수 초 제거만 해제(플래그 `False`). 함께 묶여 있던 60초 백데이트(`_DODO1_START_BACKDATE`)는 시계 오차 마진이라 `if` 밖으로 빼 **무조건 적용**으로 존속 |
| **B** | `55c589f` | TEMP `NCOF_LENIENT_INGEST` — 관대 수신 진단 계층 | 🟡 **유일하게 남은 임시 패치** |
| **C** | `f614abd` → `2a46b75` | TEMP `notificationURI` 오타 IP 치환 | ✅ **2026-09-10 17:30 제거.** 두두원이 `poc_test.ncof_sub_profile` 을 고쳐 불필요해졌다 |

### 커밋 `53e8068` — 하위 NF 구독 400 해결

`prototype/nncof-server/src/nncof/core/subscription_request_builder.py`

| 위치 | 변경 | 효과 |
|---|---|---|
| `:248` | `servive_name` 값 `"nsmf-event_exposure"`(밑줄) → `"nsmf-event-exposure"`(하이픈) | SMF 향 2건(#2,#6) 400 해소 |
| `:464-465` | `af_event_exposure.data_acc_prof_id = "dap-001"` / `ricf_… = "dap-002"` 추가 | AF/RICF PERF_DATA 2건(#3,#4) 400 해소 |
| `:467` | `ricf_event_exposure.supp_feat = "FF"` 추가 | 대칭성(400 과 무관) |
| `:346`, `:525` | `"PEF_FLOW"` → `"PER_FLOW"` | TS 29.508 enum 준수(**400 원인 아니었음**) |

> 📌 **2026-09-10 정정.** `servive` 는 **오타가 아니라 규격 그대로다.**
> `TS29508_Nsmf_EventExposure_PoC_ETRI_DoDo1.yaml:391` 이 프로퍼티를 실제로 `serviveName` 으로 선언하고,
> description 에 *"The serviveName property corresponds to the serviceName in the main body of the
> specification"* 이라고 명시한다. 값 `"nsmf-event-exposure"` 도 `SupplementaryData#ServiceName` enum 에 있다.
> 이전 판의 "양측이 같은 오타를 공유하는 상태" 라는 서술은 틀렸다 — 건드리면 안 된다는 결론만 맞았다.
> 두두원도 규격대로 `"serviveName"` 으로 찾는다(`ncof_flow_common.cpp:411`,
> `ncof_flow_subscription_handlers.cpp:56`). **`serviceName` 으로 "고치면" 연동이 깨진다.**

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
# 양측 시계 오차 마진 — 소수 초 우회와 무관한 별개 사안이라 **무조건** 적용한다.
# 규격상 무해하고(startTime 이 60초 과거일 뿐), 두두원은 미래 start 를 거절하지 않고
# 전송만 미룬다(`ncof_flow_subscription_core.cpp` 의 next_send_epoch 분기).
_DODO1_START_BACKDATE = timedelta(seconds=60)

# TEMP(두두원 연동 우회) — 2026-09-17 회수. True 로 되돌리면 마이크로초를 다시 제거한다.
_DODO1_NO_FRACTIONAL_SECONDS = False
...
    # 시계 오차 마진은 플래그와 무관하게 항상 적용한다.
    start = now - _DODO1_START_BACKDATE
    if _DODO1_NO_FRACTIONAL_SECONDS:
        start = start.replace(microsecond=0)
        stop = stop.replace(microsecond=0)
```

> 위 블록은 `ce71818` 적용 후의 **현재 소스**다
> (`subscription_request_builder.py:70`·`:89`·`:109-114`).
> 도입 시점 `131cc03` 은 플래그가 `True` 였고 백데이트가 `if` 안에 묶여
> `start = (now - _DODO1_START_BACKDATE).replace(microsecond=0)` 한 줄이었다.

`targetPeriod` 를 싣는 구독은 SMF 향 2건뿐이고, 두두원에서 `start_epoch` 을 계산하는 핸들러도
3/3p·7/7p 뿐이라 두 집합이 겹쳐 **"NEF 통지 4종은 오는데 UPF 계열만 0건"** 이라는 증상이 나왔다.

**검증(도입 시):** 적용 후 두두원이 `8_NotificationData_from_UPF_to_NCOF_v1.0.tmpl` 을 60초 주기로
발송 시작 (2026-09-09 23:35:15 최초 확인, `captured/8_NotificationData_…_pretty.json`).

> ✅ **패치 A 회수 완료 (2026-09-17 20:35, 커밋 `ce71818`).** 두두원이 10:02 빌드에서 파서를 고쳤다.
> ```c
> (구) sscanf(t, "%d-%d-%dT%d:%d:%d%c%d:%d")
> (신) sscanf(t, "%d-%d-%dT%d:%d:%lf%c%d:%d")  + sec = (int)sec_d
> ```
> 동일 코드를 떼어 컴파일·실행해 **소수 초 유무 양쪽 다 `ret==9`** 를 유지하고 epoch 오차가 0초임을
> 확인했다(구 파서 대비 −32,400초 델타).
>
> **회수 방식이 핵심이다 — 플래그 하나가 서로 무관한 두 완화를 묶고 있었다.**
> (a) 마이크로초 제거(두두원 파서 우회)와 (b) `startTime` 60초 백데이트(양측 시계 오차 마진)를
> 같은 `if` 가 게이트하고 있어, 플래그만 뒤집으면 (b)까지 사라져 **회수 후 실패했을 때 원인이
> 소수 초인지 시계 오차인지 구분할 수 없다.** 그래서 백데이트를 `if` 밖으로 빼 무조건 적용으로
> 바꾼 뒤 플래그를 False 로 내렸다. 실측 시계 편차는 −0.034초.
>
> **실기동 검증 (2026-09-17 20:27, MODE=DEVICE, 실장비):**
> 나간 `startTime: 2026-09-17T20:26:54.615759+09:00` (소수 초 실림 + 구독 생성 20:27:54 대비 정확히 60초 과거),
> UPF 주기 리포트 5분간 20건(4.0건/분, 기준선 4.30건/분, 결측 0), RICF·AF 각 15건,
> `[ERROR]` 0건 · 422 0건. **구 파서였다면 `start_epoch` 이 +9시간 미래로 잡혀 0건이어야 한다.**
>
> **되돌리기:** `_DODO1_NO_FRACTIONAL_SECONDS = True` 한 줄. 백데이트는 그대로 유지된다.
> 테스트 `prototype/nncof-server/tests/test_target_period.py` 4건이 이 분리를 고정한다
> (이 함수는 여태 테스트가 0건이었다).

### 커밋 `55c589f` — 관대 수신 진단 계층 (패치 B)

- **신규** `prototype/nncof-server/src/nncof/core/lenient_ingest.py` (402줄)
- **수정** `prototype/nncof-server/src/nncof/main.py` — import 1줄 + `install_lenient_ingest(app)` 1줄

`NCOF_LENIENT_INGEST=1` 일 때만 활성화되는 **순수 ASGI 미들웨어**. 두두원 통지의 스키마 위반을
전부 기록하고, 알려진 결함을 수리해 정상 라우트로 흘려보낸다.

핵심은 **오류 주도 수리** — 필드명을 추측하지 않고 모델이 낸 오류 지점에 후보값을 넣어보고
오류가 사라지는 것을 채택한다. 그래서 규격이 제각각인 필드가 자동으로 구분된다:

| 액션 | 예 | 2026-09-17 발동 |
|---|---|---|
| `DROP_SENTINEL` | `dlAverageThroughput: "-999"` → 필드 삭제 | **38,288회** |
| `ROUND_TO_INT` / `CEIL_TO_INT` | `pdb: 0.45` → `1` | **2,960 / 2,760회** |
| `STRINGIFY_BITRATE_BPS` | `150000000` → `"150000000 bps"` | ✅ **0회** — 두두원이 직접 실음(코드는 존치) |
| `STRINGIFY_PACKETRATE_PPS` | `500000` → `"500000 pps"` | ✅ **0회** — 〃 |
| `STRINGIFY_VOLUME_BYTES` | `9000000000` → `"9000000000 B"` | ✅ **0회** — 〃 |

> 관측창이 서로 달라 절대 건수를 그대로 비교하면 안 된다. 9/16 은 00:00–12:51(그 뒤 통지 끊김),
> 9/17 은 10:07–15:23 + 20:28–20:45(두두원 앱 15:23 정지·20:27 재기동). 아래 0회 판정은
> **9/17 첫 통지(10:07) 이후 전 구간**에 해당한다.

**✅ 단위 접미사 수리는 2026-09-17 로 불필요해졌다(요청 3 해소).** 두두원이
`src/ncof_flow_report_common.cpp:826-841` 토큰표를 `Json_Quote("50000000 bps")` /
`Json_Quote("500000 pps")` / `Json_Quote("9000000000 B")` 형태로 고쳐 단위를 직접 싣는다.
(337행이 인용한 `:527-539` 는 9/17 빌드에서 이 위치로 이동했다.)

실측 3중 대조 —
- `logs/app.log` 기준 9/16 에는 `STRINGIFY_BITRATE_BPS` 4,614 / `..._PACKETRATE_PPS` 6,152 /
  `..._VOLUME_BYTES` 3,076 회가 찍혔으나 9/17 은 세 액션 모두 **0회**.
- 9/17 raw 덤프(2,503건)의 `ulVolume`/`dlVolume` 은 2,864건 전부 `"3000000000 B"`/`"9000000000 B"` —
  옛 덤프의 맨 정수 `9000000000` 과 대비된다. 같은 페이로드 안에서 수정이 실증된다.
- 두두원 송신 덤프 `~/SBI/app/send_json/12p_c_…tmpl_pretty.json`(9/17 20:45) →
  `"dlAverageThroughput": "150000000 bps"`, `-999` **0건**. 12p_c 는 이제 **무위반 경로**라
  원장·raw 에 아예 안 남는다(관대 계층 조기 반환 — §새 사실 참고).

> 🔴 **그래도 `STRINGIFY_*` 코드를 지우지 말 것 — 회귀 감지기로 남긴다.**
> `decide_wlan_gnb2_rule._parse_mbps()`(`:164-169`, `unit = (m.group(2) or "Mbps").lower()`)는
> **단위 접미사가 없으면 Mbps 로 간주**한다. 두두원이 토큰표를 되돌려 bps 정수를 단위 없이
> 보내기 시작하면 metric 이 10⁶배 부풀려져(`300,000,000 Mbps`) gNB2 가 영구 ACTIVE 로 고정된다.
> **이 액션 카운트가 0 이 아니게 되는 순간이 곧 경보다.**

**출력:** `prototype/nncof-server/logs/lenient_ingest/`
- `ledger.jsonl` — 위반·수리 전수 원장 (두두원 보고서 원본 데이터)
- `*.raw.json` — 수리 전 원본 보존

**OFF 검증 완료:** 환경변수 없으면 미들웨어 0개, 기존 동작 그대로(422), 덤프 디렉터리도 안 만듦.
### 패치 B 회수 조건 (2026-09-17 기준 — **남은 임시 패치는 이것 하나뿐**)

패치 A 는 `ce71818` 에서 회수됐다(위 `131cc03` 절 참조). 이제 임시 패치는 B 하나다.

지금 `NCOF_LENIENT_INGEST` 를 끄면 수신 통지의 **70.1%(2,384/3,403)가 422** 다.
집계 구간은 두두원 9/17 재빌드 이후의 `2026-09-17 10:07:07 ~ 15:23:01`(앱 정지 시각까지),
근거 원장은 `logs/lenient_ingest/ledger.jsonl.upto-20260917-202439` 다. 원인은 정확히 둘이다.

| # | 원인 | 영향 통지 | 내역 | 두두원 측 근거 |
|---|---|---|---|---|
| ① | `-999` 센티넬 | 2,384건 (**100%**) | af 1,021 · upf 682 · ricf 681 | `ncof_flow_targeting.cpp:21-28`, `:56-68`, `:83-91`, `:100-107` / `ncof_flow_report_common.cpp:345,363,382,908,911,1219` / `ncof_flow_dynamic_report.cpp:289,311` |
| ② | 정수 필드에 소수값 | 1,363건 (40.1%) | upf 682 · ricf 681 (**af 는 0건**) | 3GPP 표준 필드만으로 1,362건 |

> ⛔ **①②는 동시에 고쳐야 한다.** ①만 먼저 고치면 AF PERF_DATA **682건**(af 1,021건 중
> `pdb`·`pdbDl`·`plr`·`maxPdbDl`·`maxThrputDl` 등 20개 필드가 **전부 `-999`** 라 지금은 ②가
> 드러나지 않는 통지. 나머지 339건은 볼륨 3필드뿐)이 ②로 넘어와 영향이 **최대 2,045건
> (1,363 + 682)까지 늘어난다.** "하나씩 고치자" 는 제안은 거절해야 한다.

**지금 줄일 수 있는 것과, 아직 건드리면 안 되는 것.** `_candidates()`(`lenient_ingest.py:110~`)
갈래별 실측은 이렇다.

| 갈래 | 9/17 구간 | 9/9~9/16 누적(회전 원장 전수) | 조치 |
|---|---|---|---|
| `_drop_sentinels()` (:82-105) | 2,384건 | `DROP_SENTINEL` 1,745,886 | **유지** — ①이 해소될 때까지 |
| `int_type` (:115-121) | 1,363건 | `ROUND_TO_INT` 428,451 · `CEIL_TO_INT` 118,168 | **유지** — ②가 해소될 때까지 |
| `string_type` (:123-132) | **0회** | `STRINGIFY_VOLUME_BYTES` 154,664 · `STRINGIFY_PACKETRATE_PPS` 120,664 · `STRINGIFY_BITRATE_BPS` 90,498 (마지막 발동 **9/16 12:51**) | **아직 지우지 말 것** — 아래 참조 |
| `value_error` (:134-141) | 0회 | 전 기간 채택 **0건** | 지워도 동작 동일(9줄, 이득 작음) |

> 🔴 **`string_type` 갈래의 "0회" 는 지우라는 신호가 아니라 감시 대상이다.**
> 이 갈래가 멎은 것은 두두원이 **9/17 10:02 재빌드로 요청 3(단위 접미사)을 고친 직후부터**이고,
> 무발동 관측 구간은 통틀어 **5시간 16분 + 재기동 후 17분** 뿐이다. 더구나 ①이 해소되면 지금
> `-999` 에 가려진 스루풋 필드(8p 주기보고 682건의 8필드 포함)가 실값으로 바뀌는데, 그 값이
> 단위 접미사를 달고 오는지는 **회선에서 아직 한 번도 확인된 적이 없다.** 접미사 없이 오면
> 위 🔴 `STRINGIFY_BITRATE_BPS` 문단의 10⁶배 오해석 문제가 그대로 되살아난다.
> 따라서 지우지 말고, 원장에 `STRINGIFY_*` 가 다시 찍히는지를 회귀 신호로 감시하라.

> 📎 `value_error` 갈래의 "0회" 는 **갈래에 진입하지 않았다는 뜻이 아니다.** `-999` 가 BitRate
> 정규식을 못 넘겨 `value_error` 자체는 지금도 난다(원장 `before_summary` 에 `[36회] value_error`).
> 다만 `:137` 의 `head.replace(".", "", 1).isdigit()` 이 음수 문자열을 걸러 후보가 빈 채 반환되므로
> `RETRY_PACKETRATE_PPS`/`RETRY_BITRATE_BPS`/`STRIP_UNIT` 가 **한 번도 채택된 적이 없다.**

> 📌 **"원장에 없다 = 안 왔다" 가 아니다.** 관대 계층은 `lenient_ingest.py:358-359` 에서
> `report["before_error_count"] == 0` 이면 **조기 반환**한다. 즉 **무오류 통지는 `ledger.jsonl` 에도
> `*.raw.json` 에도 남지 않는다.** 9/17 에 `13p_d` raw 덤프가 0건이 된 것은 통지가 끊긴 게 아니라
> **전수 통과했다는 증거**였다. 수신 여부는 원장이 아니라 `app.log` 의 `[NOTIFICATION]` 으로 세라.

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
> 나머지 읽기 지점 2곳(`subscription_manager.py:335`, `utils.py:131→:186`)은 GUI 에코일 뿐이다.
> 따라서 **다른 곳에 오타 IP 가 남아 요청이 새는 경로는 없다.**

---

## 5. 현재 파이프라인 상태 — **제어 루프 관통 재확인 (2026-09-17 20:27 재기동 기준 실측)**

> 최초 관통 실증은 2026-09-10 09:39 이었다(아래 `captured/…2026-09-10…` 본문이 그때 것이다).
> 이 표는 두두원 9/17 수정 반영 후 **20:27:54 재기동분**으로 전부 다시 잰 값이다.

| 단계 | 상태 |
|---|---|
| PCF/RICF → NCOF 구독 (20:27:54 / 20:27:58) | ✅ 핸들러 2건 기동 (`fa771700…` / `13f31868…`) |
| NCOF → SMF/AF/RICF 팬아웃 10건 | ✅ 전부 HTTP/2 200 (비200 0건) |
| 두두원 → NCOF 통지 발송 | ⛔ **20:45:05 에 멎었다** — 20:27~20:45 은 60초 주기 6종(`8_`, `9_`, `10_a`, `11p_b`, `12p_c`, `13p_d`) 정상(UPF 68 / AF 51 / RICF 51건). 그 뒤 무음 (아래) |
| NCOF 수신·파싱 | ✅ **422 0건** — 단, 관대 수신이 119건을 수리한 결과다(잔여 0건). `13p_d` 도 통과 (아래) |
| 저장 → 분석 → gNB2 판정 | ✅ `분석 메트릭 WLAN_DL_MBPS:150.0` → `CELL_POWER_STATE: DEEP_SLEEP` |
| ~~TEMP URI 치환 (패치 C)~~ | ✅ **불필요** — 두두원이 오타를 고쳐 2026-09-10 17:30 제거 (§4) |
| TEMP 소수 초 제거 (패치 A) | 🟢 **절반 회수** — 두두원이 파서를 고쳐 소수 초 제거만 해제(`ce71818`, 9/17 20:35). **60초 백데이트는 플래그 밖에서 상시 적용 중**(`subscription_request_builder.py:89`, `:110-111`) |
| TEMP 관대 수신 (패치 B) | 🟡 **가동 중** — 끄면 70.1% 422 (§4·§6) |
| **NCOF → PCF 제어 발송 (20:28:58)** | ✅ **HTTP/2 200 수락** |
| **NCOF → RICF 제어 발송 (20:29:06)** | ✅ **HTTP/2 200 수락** (`_cellPowerState: DEEP_SLEEP`, `gNBValue: 000002`) |
| 두두원 → 실장비 UPF 로 QoS UDP 발사 | ❓ **NCOF 가시성 0** — 보낸 14_e 에 `GBR_DL` 4세트가 실린 것까지만 확인. 실제 발사 여부는 미확인 |
| 두두원 → gNB2 `cell-stop` SSH | ❓ 읽기 전용 제약으로 미확인 (§8) |
| RICF 가 `cell_power_state` 를 에코 | ⛔ **에코 기능이 존재하지 않는다** (아래) |

`[ERROR]` 0건 · `제어명령 실패` 0건 · `422` 0건 (20:27 이후 전 구간, `logs/app.log:818697` 이하 전수).

**제어는 각 1회뿐이다.** 20:27~20:45 사이 분석은 48회(150.0 이 39회, 0.0 이 9회) 돌았지만
`[제어명령] ---> [PCF]`·`---> [RICF]` 는 **각 1건**이다. §8.1 에 적은 emit-on-change 게이트
(`gnb2_rule_engine.py:47-49`)가 상태가 안 바뀌면 `None` 을 돌려주기 때문이며, 정상 동작이다.
**"관통이 매 주기 반복된다" 고 읽지 말 것.**

### ✅ `13p_d` 422 는 해소됐다 — 다만 판정 근거를 헷갈리지 말 것

두두원이 요청 2(13p_d 구조 4종)를 9/17 에 고쳐 **잔존 위반 0건**이 됐다. 근거는 이렇다:
`_POWER_ENERGY_CONSUMPTION`/`_RF_SIGNAL` 를 포함한 `logs/lenient_ingest/*.raw.json` 덤프가
**9/16 770건 → 9/17 0건**이다. 9/17 20:27 이후 덤프 119건은 전부 `PERF_DATA`/`DISPERSION` 계열이다.

> ⚠️ **원장에 `NncofEventsSubscriptionNotification` 이 없다는 것은 근거가 되지 못한다.**
> 관대 계층은 그 모델명을 **원리적으로 기록할 수 없다** — `lenient_ingest.py:294-300` 의
> `_model_for()` 가 `NotificationData`(경로 `/notifications/upf/…`) 아니면 `NefEventExposureNotif`
> **둘만** 돌려주고, 원장의 `model` 필드는 `:224` 에서 `model_cls.__name__` 으로 채워진다.
> `13p_d` 는 파일명이 `…NncofEventsSubscriptionNotification…` 일 뿐 실제로는
> `/notifications/ricf/{id}` 로 들어와 `NefEventExposureNotif` 로 검증된다(§6.1 의 "RICF 통지 689건" 과 동일 경로).
> 그리고 **무오류 통지는 원장·raw 덤프에 아예 안 남는다**(`lenient_ingest.py:353-356` 조기 반환).
> 즉 "원장에 없다" 는 "안 왔다" 가 아니라 **"수리할 게 없었다"** 는 뜻이다.

### ⛔ 두두원 앱이 20:45:05 에 또 멎었다 — 원인 미확인

20:27 재기동 후 18분만에 다시 정지했다. 2026-09-17 21:02 확인:

- `ssh dodo1` 에 **`sbi_poc_app` 프로세스가 없다**. `ss -lntp` 에 **55555/55556/55557/55558 리스닝이 없다**.
- `send_json/` 8개 파일이 **20:45:01~20:45:05 에 얼어붙어** 그대로다.
- NCOF 마지막 통지 수신은 `app.log:860374` **20:45:05**. 이후 로그는 NCOF 자체 주기 분석뿐이다.
- ⚠️ **요청했던 `tee ~/SBI/app/sbi_poc_app.<날짜>.log` 가 적용되지 않았다** — `/home/dodo1/SBI/app/` 에
  `*.log` 가 하나도 없다. 그래서 15:23 정지와 **똑같이 원인을 남길 로그가 없다.**
  운영자 세션(`10.254.73.20`)은 15:18 부터 계속 붙어 있다.

**→ 재측정·재현을 하려면 두두원 재기동이 선행돼야 한다. 순서는 §8.1 "청소 후 재기동" 을 따를 것.**

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

### 분석 메트릭이 0.0 / 150.0 두 값만 오간다 (~~300.0~~ 은 2026-09-16 이후 소멸)

- NCOF 는 구독 1건마다 **UPF 스트림을 2개** 만든다(SERVICE_EXPERIENCE, WLAN_PERFORMANCE).
  둘 다 `/notifications/upf/<sub_id>` 로 오고(`subscription_request_builder.py:271`),
  같은 store 에 **서로 다른 correlationId 로** 쌓인다(`subscription_handler.py:413`, `:423`, `data_store.py:42`).
  두두원 쪽에서 이 둘은 kind **3/3p**(`8_` 템플릿)와 kind **7/7p**(`12p_c` 템플릿)다(§4 참조).
- `_get_wlan_performance_data()`(`data_analyzer.py:198-227`)가 **UDUM `timeStamp` 가 가장 최신인 것 하나**를
  고른다. 두 템플릿의 `dlAverageThroughput` 이 달라서 산출값이 두 개로 고정된다 —

  | 송신 템플릿 | 두두원 kind | `dlAverageThroughput` | 산출 metric |
  |---|---|---|---|
  | `8_NotificationData_from_UPF…` | 3/3p | UDUM **4건 전부 `"-999"`** | `0.0` |
  | `12p_c_NotificationData_from_UPF…` | 7/7p | UDUM 1건 `"150000000 bps"` | `150.0` |

- **이전 판의 "SERVICE_EXPERIENCE 60초 / WLAN_PERFORMANCE 120초" 는 틀렸다 — 두 스트림 다 60초다.**
  두두원이 보낸 구독 원본(`send_json/1_…json`, `1p_…json`)에서 두 이벤트 모두 `repetitionPeriod: 60`
  이고 상위 `evtReq.repPeriod` 도 60 이다. `app.log` 의 `[UPF] --- [NOTIFICATION]` 도 분당 4건
  (구독 2개 × 스트림 2개)이 전부 60초 간격이다.
  > ⚠️ 이 검증에 **원장(`logs/lenient_ingest/`) 도착 시각을 쓰면 안 된다.** 파일명 태그는 correlationId 가
  > 아니라 URL 경로의 `sub_id` 이고, 9/17 단위 수정 이후 `12p_c` 는 무오류라 **원장에 아예 남지 않는다**
  > (`lenient_ingest.py:358-359` 조기 반환). 그래서 원장 UPF 는 분당 2건(`8_` 만)으로 보이고,
  > 원장만 보면 7/7p 스트림의 주기를 확인할 수 없다.
- **진짜 변수는 주기가 아니라 위상이다.** 분석 타이머가 같은 회차의 `8_` 도착과 `12p_c` 도착 **사이**에
  끼면 그 회차만 `0.0` 이 된다. 그래서 같은 9/17 안에서도 양상이 갈린다 —

  | 구간 | 분석 레인 | 값 |
  |---|---|---|
  | 09-17 00:00–09:59 | `:00` | **0.0 고정** (600/600, 진동 0회) |
  | 09-17 00:00–09:59 | `:02`/`:03` | **150.0 고정** (600/600, 진동 0회) |
  | 09-17 20:28–20:52 | `:58` | 0.0 ↔ 150.0 **진동** |

  20시 레인의 진동은 두두원 송신이 분당 약 +0.3초씩 밀리며 `:58` 분석 시각을 넘나든 결과다
  (`8_` 도착 20:34:57.49 → `0.0`, 20:40:58.90 → `150.0`).
  → **이전 판의 "구독 간 차이가 아니라 주기 간 진동" 은 절반만 맞다.** 위상에 따라 둘 다 나타난다.
- `0.0` 은 "선택된 통지의 `dlAverageThroughput` 이 전부 `-999` 센티넬이라 관대 수신이 필드를 지웠다" 는 뜻이다.
- ~~`300.0`~~ **해소됨 (2026-09-16 11:59:01 이후 관측 0건).** `logs/app.log` 계열 실측 —

  | 날짜 | 0.0 | 150.0 | 300.0 |
  |---|---|---|---|
  | 2026-09-14 | 453 | 1,997 | 430 |
  | 2026-09-15 | 232 | 2,440 | 207 |
  | 2026-09-16 | 736 | 2,081 | 62 |
  | **2026-09-17** (20:52 시점) | **2,487** | **3,685** | **0** |

  `300.0` 은 **한 통지 안에서 비-센티넬 dl 값이 2개 살아남아** `extract_wlan_dl_mbps()` 의 합산
  (`total += _parse_mbps(...)`, `decide_wlan_gnb2_rule.py:186-187`)이 두 번 더해질 때 나왔다
  (구 원장 예: dl 리스트가 `['-999', 150000000, '-999', 150000000]`).
  지금 회선의 `8_` 은 dl 4건이 전부 `-999`, `12p_c` 는 dl 이 1건뿐이라 그런 통지가 만들어지지 않는다.
  **원인이 사라진 것이지 합산 로직이 고쳐진 것은 아니다** — 두두원이 dl 을 둘 이상 실어 보내면 재발한다.
- **`0.0` 은 무해하지 않다.** PCF 구독에서 `0.0` 이 DEEP_SLEEP 판정을 만들고 그게 PCF 향 QoS 정책
  제어 명령으로 나갔다. 다만 `data_analyzer.py:269` 의 `nf_type == "RICF"` 게이트가 PCF 를 cell-power
  분기에서 막아 주므로 gNB2 전력 판정 자체가 오염되지는 않는다.
- **지금의 판정은 어느 값이어도 같다** — `0.0` / `150.0` 둘 다 `TH_MBPS = 500.0`
  (`decide_wlan_gnb2_rule.py:88`) 미만이라 모두 DEEP_SLEEP. 즉 당장 오판을 만들지는 않지만 잠재 결함이다.
- 덧붙여 **`150.0` 은 실측값이 아니다.** 회선 위의 비-센티넬 throughput 은 전부 템플릿 상수다.
  9/17 단위 접미사 수정 전에는 `12p_c` 가 맨숫자 `150000000` 을 보냈고 관대 계층의
  `STRINGIFY_BITRATE_BPS`(`lenient_ingest.py:128-129`)가 `"150000000 bps"` 로 바꿔 줘서 결과적으로
  같은 `150.0` 이 나왔다. 지금은 두두원이 처음부터 `"150000000 bps"` 로 보낸다.

---

## 6. 두두원 수정 요청 목록

| 심각도 | 항목 | 근거 |
|---|---|---|
| ~~치명~~ **해결** (2026-09-10 17:16) | ~~구독 `notificationURI` IP 오타~~ — 두두원이 `poc_test.ncof_sub_profile.uri_pcf/uri_ricf` 를 `10.254.173.46` 으로 수정. 패치 C 회수 완료 | 치환 없이 양쪽 200 재확인 |
| ~~치명~~ **해결** (2026-09-17 10:02 빌드) | ~~ISO8601 소수 초 미지원~~ — 파서가 `sscanf(t,"%d-%d-%dT%d:%d:%lf%c%d:%d")` + `sec=(int)sec_d` 로 수정됐다(`ncof_flow_subscription_core.cpp:228`, 함수 `Parse_Iso8601_Time_To_Epoch:208`. 9/11 판의 `:226` 은 재빌드로 밀린 낡은 줄번호다). 소수 초 유무 양쪽 다 `ret==9`, epoch 오차 0초(구 파서 대비 정확히 −32,400초 델타). 이 파서가 소스 전체에 하나뿐이고 호출부가 `:290`·`:301`·`:554`·`:580` 네 곳뿐이라 `expiry`·`monDur`·`validityTimes` 경로도 함께 해소. **패치 A 회수 완료**(`ce71818`) | 9/17 20:27 실기동 — `startTime: 2026-09-17T20:26:54.615759+09:00` 이 나간 뒤 UPF 주기 리포트 4.0건/분(기준선 4.30), ERROR·422 0건 |
| ~~치명~~ **해결** (2026-09-17) | ~~`_powerEnergyConsInfos` 키 이름 오류~~ — `_powerEnergyConsumptionInfos`(`TS29591:498`)로 수정됐다. 조용히 드롭되던 `_POWER_ENERGY_CONSUMPTION` 본문이 실제로 적재된다. 구 키는 `templates/send/` 전체에 **0건**. ※ 이 키를 가진 템플릿은 **2종**이다 — 통합 `13p_d_…v1.0.tmpl:134` 와 `_POWER.tmpl:8`. `_SIGNAL.tmpl` 에는 애초에 power 블록이 없다 | 341/341 적재, 배열 원소 682개, `_powerEnergyConsData` 7필드 전수 채워짐 |
| ~~높음~~ **해결 (적용 범위 부분)** (2026-09-17) | ~~throughput 을 bps **정수**로 전송~~ — 토큰표가 `ncof_flow_report_common.cpp:829` `Json_Quote("50000000 bps")` ~ `:833` `("300000000 bps")`, `:837-838` `("300000 pps")`/`("500000 pps")` 로 수정됐다. **단 `8p` 주기 보고 경로(682건)는 스루풋 8필드가 100% `"-999"` 라 이 수정과 무관하다** — 값을 채우는 곳이 토큰표가 아니라 `ncof_flow_dynamic_report.cpp:289` `Set_Json_Bps_To_Mbps` 다. 아래 `-999` 항목과 함께 봐야 한다. (9/11 판의 `:527-539`·`:524`·`:907-934` 는 §6.3 의 9/10 감사 기준 줄번호) | 10⁶배 왜곡 해소. `12p_c` 678건 정상, 분석값 `150.0 Mbps` 로 산출 |
| ~~높음~~ **해결** (2026-09-17) | ~~Volume 필드가 정수~~ — 같은 토큰표 `:840-841` 이 `Json_Quote("3000000000 B")` / `Json_Quote("9000000000 B")` 로 수정됐다 | 바이트 단위 정규식 통과 |
| ~~높음~~ **해결** (2026-09-17) | ~~`13p_d` 계열 구조적 결함 5종~~ — `timeStamp`(대소문자)·`_nodeAddrs`(배열→단일 객체)·`tai`·`ncgi`·`nrCellId` hex 9자리 5종 전부 템플릿 3종에서 수정됐다. 상세는 **§6.1**(9/17 해소 — 이력으로 보존) | 9/17 검증 창 `13p_d` **341건 수신, 잔존 위반 0건**. 직전 창에서는 940건 전량 422(§6.1 의 689건은 9/9~9/10 창 수치) |
| 🔴 **치명 — 최우선 1** | **`-999` 센티넬** — 값 없으면 **필드 생략**이 규격. 영향 통지 **2,384건(수신 3,403건의 70.1%)**, 이는 **422 거절분 2,384건 전체(100%)** 다. 근원은 `ncof_flow_targeting.cpp:21-28` `Json_Stamp_Number_Default()`, `:56-68` `Replace_Stamp_One()`(RTT/DELAY/JITTER/LOSS 8종 일괄), `:85-91` `Json_Qos_Throughput_Default()`, `:102-107` `Json_Available_Bitrate_Value()`, `ncof_flow_report_common.cpp:341-348` `Json_Metric_Number_Or_999` / `:359-366` `Json_Metric_Text_Or_999` / `:378-385` `Json_Metric_RF_With_Unit_Or_999`(9/11 판의 `:225-247` 은 재빌드로 밀린 줄번호), 같은 파일 `:908`·`:911`·`:1219`, `ncof_flow_dynamic_report.cpp:289,311`. 3GPP 타입에 "데이터 없음" 표현이 없다 — `PacketDelBudget` min 1, `PacketLossRate` 0..1000, `BitRate`/`PacketRate`/`TrafficVolume` 은 `^\d+(\.\d+)?` 패턴이라 선행 `-` 자체가 불가 | **패치 B 를 붙잡는 둘 중 하나.** 보정 계층이 지운 필드 73,352건 |
| 🔴 **치명 — 최우선 2** | **정수 필드에 소수값** — 영향 통지 **1,363건(수신의 40.1%)**, 3GPP 표준 필드만으로 1,362건. `pdb: 0.45`, `_dlMaxPacketDelay: 20.74`. `pdb`·`pdbDl`·`maxPdbUl`·`maxPdbDl`(TS 29.517), `dl/ul/rtrPacketDelay`(TS 29.508)는 정수 타입이라 관대 수신으로 완화 불가. 출처는 위와 같은 `Replace_Stamp_One()` 계열 | **둘은 동시 수정 필수.** ①만 먼저 고치면 `-999` 에 가려져 있던 AF `PERF_DATA` 682건이 ②로 드러나 영향이 최대 2,045건까지 는다. 한 번에 어려우면 **②를 먼저** |
| 중간 | **`upf_qos_udp` 경로에 NCOF 가시성이 0 이다** — 두두원이 우리 14_e `QOS_POLICY_ASSIST` 를 받으면 실장비 UPF 로 바이너리 UDP 를 직접 발사한다(`ncof_flow_control.cpp:332-336` `Send_Qos_Apply_To_Upf_Udp(config.upf_ip, config.upf_port, packet)`, `QOS_APPLY_UE_COUNT`=4 라 UE 4개가 다 차야 발사). SBI 응답은 여전히 `200` 이라 성공·실패를 알 수 없다. 활성화 여부 · UDP 실패 통보 방법 · 최소 UE 수를 확인 요청함 | 9/15 신규 모듈 `include/upf_qos_udp.h`, `src/upf_qos_udp.cpp` |
| 중간 | AF 템플릿과 RICF 템플릿의 값 생성 규칙이 서로 다름(`9_` 는 `-999`, `10_a` 는 소수) — 위 최우선 2건을 고치면 대부분 함께 해소된다 | 한 번에 고치려면 둘 다 |
| 중간 | **제어 명령 수용 결과를 관측할 방법이 없다** — 수신 15F 는 `poc_test.recvJson`/`gnb_control*` 로만 들어가고 어디서도 SELECT 되지 않으며, `send_json/` 에도 안 남는다. 최소한 수신 덤프 1개라도 파일로 남겨 주면 연동 검증이 가능해진다 | 종단 확인 불가 |
| 중간 | **HTTP 200 이 실제 gNB 제어 성공을 뜻하지 않는다** — `save_count` 는 MySQL INSERT 만으로 증가하고 SSH 셸아웃 결과를 반영하지 않는다. 셸아웃 실패를 응답 코드에 반영해 달라 | 무증상 실패 |
| 중간 | **앱이 로그를 파일로 남기지 않는다** — 9/17 15:23:01 정지의 원인을 끝내 특정하지 못한 직접 원인이다(§8). `./sbi_poc_app 2>&1 \| tee ~/SBI/app/sbi_poc_app.$(date +%F_%H%M).log` 로 기동해 달라고 요청함 | 터미널 스크롤백이 유일한 단서였다 |
| 낮음 | **gNB1·gNB2 가 동일한 `nrCellId`(`123456789`)** 를 보고한다 — 값 하드코딩이 `ncof_flow_report_common.cpp:450`(`gnb1_nr_cell_id`)·`:460`(`gnb2_nr_cell_id`)이고 주입은 `:617`·`:627` 이다. `mcc`/`mnc` 도 같아 **NCGI 기준으로는 같은 셀**이다. 형식은 규격 합격이고 지금은 `gNbId`(000001/000002)·FQDN 으로 구분하므로 제어에 지장 없으나, 셀 단위 에너지 집계를 넣으면 두 gNB 가 병합된다 | 9/17 회신에 후속 요청으로 포함 |
| 낮음 | `templates/send/` 의 공백 든 중복 파일 `8p_..._v1.0 _USER_DATA_USAGE_MEASURES.tmpl` 정리 | 참조되지 않는 잔재 — 9/17 현재 그대로 |
| 낮음 | `13p_d` 의 `_powerState` 가 템플릿 하드코딩 `"ACTIVE"` — 9/17 재작성 후 통합 tmpl `:178`·`:224`, `_POWER.tmpl` `:53`·`:100`(9/11 판의 `:149, :183` 은 재작성 전 줄번호). 제어 반영 상태를 여기에 실어 주면 NCOF 가 폐루프를 자체 검증할 수 있다 | 폐루프 검증 — 재작성 후에도 그대로 |
| 낮음 | 400 응답에 사유를 실어 달라(현재 `{"error":"bad request"}` 고정, 사유는 stderr 에만) | `http2_server.cpp:122,149,348,378,887`, `ncof_flow_subscription_core.cpp:1287` — 9/17 현재 그대로 |
| ~~높음~~ **강등 — 수정 요청 아님, 협의 항목** | ~~하위 구독 응답에 구독 ID 가 없다~~ — NCOF 가 `notifId` 폴백으로 자체 해소했고(§8 의 8), 규격이 요구하는 것은 `201` + **필수 `Location` 헤더**이지 `Subscription-ID` 가 아니다(`ncof_yaml` 전체에 `Subscription-ID` 0건). 9/17 회신에서 요청 목록에서 뺐다 | **§6.2** — 근거·경위(표의 mockup 비교는 이력으로 보존) |

### NCOF 측 자체 결함 (두두원과 무관, 우리가 고칠 것)

| 심각도 | 항목 | 근거 |
|---|---|---|
| ~~높음~~ **해결** (`1335888`) | ~~14_e(PCF 향) 제어 본문이 템플릿의 하드코딩 값을 그대로 내보낸다~~ — `apply_qos_policy()` 가 봉투를 손대지 않아 `subscriptionId`/`notifCorrId`/`resourceUri` 와 타임스탬프 29곳이 템플릿 고정값(2026-03-01)으로 나갔다. `build_15f_cell_power()` 와 같은 시그니처로 맞추고 `sub_id`/`corr_id`/`decision_iso` 로 전부 덮어쓰도록 수정. **11:11 실기동 재확인: 잔존 0건, 양쪽 200** | `captured/14_e_control_NCOF_to_PCF_{BEFORE,AFTER}_envelope_fix.json` |
| 높음 | metric 진동 (§5) — 한 구독의 두 UPF 스트림 중 "최신 UDUM" 하나만 골라 쓴다 | `data_analyzer.py:213-227` |
| 중간 | `data_analyzer.py:184-185` 필터가 NEF/UPF 경계는 긋지만 **WLAN/비-WLAN 경계는 긋지 않는다** | 아래 §7 참조 |
| ~~높음~~ **해결** (`e49c613`) | ~~`external_subscriptions` 가 항상 비어 고아 구독이 쌓인다~~ — 응답에 ID 가 없으면 요청 본문 `notifId` 를 채택. 실장비 해지 10/10 → 200 실증. §8 의 8 | `subscription_handler.py:141-165` |
| ~~중간~~ **높음** (2026-09-17 실증) | **중복 구독 제거가 없다** — `create_subscription`(`:92-103`)이 `uuid4()` 를 조건 없이 발급하고(`:99`) 무조건 삽입한다(`:103`). **9/17 오전 두두원이 3회 재기동(10:02:57 / 10:05:01 / 10:20:18)하며 매번 구독을 재전송해 구독 트리가 4벌 쌓였다** — 상향 8 / 하위 40(NCOF 기록상. 장비 실재는 10) / GUI 간선 72, 기준선 2/10/18 의 정확히 4배다. §8.1 이 **코드 검증만으로** 적어 둔 "두두원 만 재기동" 시나리오가 **처음으로 회선에서 실증된 것**이다. 통지 물량과 제어 명령은 늘지 않고(§8.1 정정) 분석 타이머만 4배로 돈다. 20:24 "청소 후 재기동" 으로 2/10/18 복구. **코드는 그대로다** — `e49c613` 이후 이 파일은 한 줄도 바뀌지 않았고, `e49c613` 이전에도 동일한 사전 결함이었다. 보완 전까지는 두두원에 "재기동 시 사전 공유" 협조를 요청해 둔 상태(9/17 회신 §4) | `subscription_manager.py:92-103`, 절차 방어는 §8.1 |
| 중간 | **`monDur` 타임존 미정규화** — `data_analyzer.py:132-138` 이 `evt_req.mon_dur` 를 naive/aware 정규화 없이 `datetime.now(timezone.utc)` 와 비교한다(`subscription_manager._is_expired:446-450` 은 정규화한다). 오프셋 없는 `monDur` 이 오면 첫 루프에서 `TypeError` 로 분석 태스크가 죽고, 유일한 예외 처리가 `except asyncio.CancelledError` 뿐이라 **조용히 사라진다** — GUI 에서 건강한 핸들러와 구분 불가. 두두원은 오프셋을 붙여 보내므로 현재 미발동 | `data_analyzer.py:132-138`, `:162-163` |

### 6.1 `13p_d` 구조적 결함 5종 — ~~자동 수리 불가~~ **전건 해소 (2026-09-17)**

**대상**: `/home/dodo1/SBI/app/templates/send/` 의 `13p_d_…v1.0.tmpl`(9/17 01:50), `…_POWER.tmpl`(01:45), `…_SIGNAL.tmpl`(01:46) **3개 모두 재작성 확인**. 다만 회선으로 실증된 것은 **통합 `.tmpl` 1종뿐**이다 — `ncof_flow_subscription_core.cpp:101-128` `Select_2p_Report_File()` 이 `_RF_SIGNAL` 과 `_POWER_ENERGY_CONSUMPTION` 을 **둘 다** 요청한 구독에는 통합본을 고르고, NCOF 는 항상 둘 다 구독한다. 단독 2종은 파일 수준 확인에 그친다.
**규격 근거**: `generated/nnef/openapi.yaml`(양측 합의 규격), 3GPP TS 29.571 / TS 38.413
**최초 실측**: 2026-09-09~09-10 RICF 통지 **689건** 수신분 (`logs/lenient_ingest/ledger.jsonl`)
**직전 실측**: 2026-09-09 23:49 ~ 09-11 07:26 **940건 전량 422**. 고치기 직전 24시간(9/16)도 **770건 전량 422** (`logs/lenient_ingest/` 의 9/16 ricf raw 2,308건 = `PERF_DATA` 1,538 + `_POWER_ENERGY_CONSUMPTION` 770 + `_RF_SIGNAL` 770)
**검증 실측**: 2026-09-17 10:07:06~15:22:51 `13p_d` **341건 전건 스키마 통과, 잔존 위반 0건**. 같은 창의 ricf raw 덤프 715건은 **전부 `PERF_DATA`** 로, `13p_d` raw 덤프는 **0건**이다 — 관대 계층은 무오류 통지를 덤프하지 않으므로(`lenient_ingest.py:353-356`) 이 0 이 곧 전수 통과의 증거다

| # | JSON 경로 | 당시 값 | 규격 | 당시 건수 | 9/17 검증 (341건 기준) |
|---|---|---|---|---|---|
| 1 | `eventNotifs[].timeStamp` | 키가 **`timestamp`**(소문자 s) | `timeStamp` — **필수**, 대소문자 구분 | 1,378 | ✅ 해소 — `NefEventNotification` **682/682** 정상 파싱. 9/17 raw 덤프 2,503건 전체에도 소문자 `timestamp` **0건** |
| 2 | `eventNotifs[]._rfSignalInfos[]._nodeAddrs` (및 `._powerEnergyConsumptionInfos[]._nodeAddrs`) | **배열** `[{…}]` | `$ref: AddrFqdn` — **단일 객체**. `TS29591…yaml:736`(`_RfSignalInfo`)·`:879`(`_PowerEnergyConsumptionInfo`) → `SupplementaryData…yaml:1384-1386` `AddrFqdn` / `type: object` | 1,378 | ✅ 해소 — 단일 객체 **1,364/1,364**, 배열 **0건** |
| 3 | `…_loc.nrLocation.tai` | **키 없음** | `NrLocation.required: [tai, ncgi]` (`TS29571…yaml:2437-2439`) | 1,378 | ✅ 해소 — **1,364/1,364** 존재, `None` 0건 |
| 4 | `…_loc.nrLocation.ncgi` | UE1 에 **키 없음**(UE2 는 있음) | 위와 동일 | 689 | ✅ 해소 — **1,364/1,364** 존재, `None` 0건 |
| 5 | `…_loc.nrLocation.ncgi.nrCellId` | `"cell-002"` | `^[A-Fa-f0-9]{9}$` (36비트 hex 9자리, TS 38.413 §9.3.1.7 — `TS29571…yaml:1382-1384`) | 689 | ✅ 해소 — **1,364건 전부 `"123456789"`**, 형식 위반 **0건** |

> 건수 단위가 행마다 다르니 주의하라. 341건 × **이벤트 2종** = `eventNotifs` **682**(1번 행), 341건 × **정보 원소 4개**(`_rfSignalInfos` 2 + `_powerEnergyConsumptionInfos` 2) = **1,364**(2~5번 행). 회신 발송본(`두두원_회신_발송본.md:48`)은 3·4번을 682 로 적었는데 **실측은 1,364 다** — 발송본 쪽이 절반으로 잘못 세었다.

당시 건수는 `689건 × (UE 2개 또는 이벤트 2종)` 으로 전부 정합했다. 1번은 값 형식이 아니라 키 이름 문제였고, 두두원이 키 이름만 고쳐 해결했다. 덧붙여 같은 재작성에서 §6 의 **치명** 항목이던 `_powerEnergyConsInfos` → `_powerEnergyConsumptionInfos` 키 이름도 함께 고쳐졌다(현재 `13p_d_….tmpl:134`, `_POWER.tmpl:8`).

> ⚠️ **후속 1건 — `nrCellId` 가 gNB1·gNB2 동일**. 형식은 합격이나 두 gNB 가 똑같이 `"123456789"` 를 쓰고 `mcc`/`mnc` 도 같아 **NCGI 상 같은 셀로 식별**된다. 원인은 `ncof_flow_report_common.cpp:450`·`:460` 이 `gnb1_nr_cell_id`/`gnb2_nr_cell_id` 를 같은 기본값으로 두고, DB `nr_cell_id` 컬럼이 비면 그대로 나가기 때문이다(`:505`, `:537` → 치환 `:617`, `:627`). 지금은 NCOF 가 `gNbId`(000001/000002)·FQDN 으로 구분하므로 제어에 지장은 없으나 **셀 단위 에너지 집계를 넣으면 두 gNB 가 병합된다.** 9/17 회신으로 gNB 별 상이한 값을 요청해 둔 상태다.

> ~~⚠️ 2번은 `_` 접두 **확장 필드**다. "복수 노드를 실어야 한다"는 의도라면 배열이 맞고 우리 규격/모델을 바꾸는 게 옳다. 어느 쪽이 의도인지 회신을 받아야 한다~~ → **닫힘.** 애초에 §7(`_nodeAddrs` 는 배열이 맞다 = 반증됨)에서 이미 **객체가 맞다**고 결론이 나 있었다(`ncof_yaml` 커밋 `26057fa`, 2026-05-26 "fix _nodeAddrs array to object"). 이 ⚠️ 는 §7 과 모순된 채 남아 있던 잔재였고, 9/17 에 두두원이 단일 객체로 고쳐 보내면서 사실로도 닫혔다.

> ~~**왜 관대 수신이 못 고치는가**: `tai`/`ncgi` 의 TAC·셀 ID 를 지어낼 수 없고, `"cell-002"` 에서 올바른 hex 를 유도할 근거가 없으며, `_nodeAddrs` 는 첫 원소만 취해도 되는지 합의가 필요하다. 키 이름 오타(`timeStamp`)는 오탐 위험 때문에 추측 수리 대상에서 의도적으로 제외했다.~~ → **역사적 기록.** 발신 측 수정 없이는 수신 측 보정이 불가능하다는 판단이었고, 실제로 발신 측 수정으로 풀렸다. 같은 상황이 또 오면 이 판단을 재사용하라.

**영향**: ~~`13p_d` 는 **현재 100% 거절**된다.~~ → **2026-09-17 10:02 두두원 바이너리 재빌드로 해소.** 이제 `13p_d` 도 전건 통과하며, `_powerEnergyConsData` 7개 필드가 실제로 적재된다(341/341, 배열 원소 682개). **이 절은 더 이상 패치 B(`NCOF_LENIENT_INGEST`) 회수를 막는 요인이 아니다** — 남은 차단 요인은 `-999` 센티넬과 정수 필드 소수값 둘뿐이다.

> 📌 **`_nodeAddrs` 는 단일 객체가 맞다 — 2026-09-17 해소, 논쟁 종결.** 이전 판에 "복수 노드를 실어야 한다는 의도라면 배열이 맞으니 어느 쪽인지 회신을 받아야 한다" 는 주석이 있었으나, **이미 2026-05-26 에 종결된 사안을 미결로 적은 낡은 서술**이었다(§7 과 정면 모순). 근거: `ncof_yaml` 커밋 `26057fa`(2026-05-26) "fix _nodeAddrs array to object" 가 우리 참조 샘플 `ncof_json/13p_d_…v1.0.json` 의 4곳(`_rfSignalInfos` 2 + `_powerEnergyConsInfos` 2)을 `[{…}]`→`{…}` 로 고쳤고, 규격도 `TS29591_Nnef_EventExposure_PoC_ETRI_DoDo1.yaml:736`·`:879` 가 `$ref: AddrFqdn` → `SupplementaryData_PoC_ETRI_DoDo1.yaml:1384-1386` `type: object` 다. 규격·샘플 양쪽이 단일 객체로 일치한다. 배열로 보이던 파일은 `.claude/worktrees/*` 의 5/4 자 옛 스냅샷이다(§7, §9). 두두원도 9/17 수정본에서 단일 객체로 바꿨고 회선 실측 **1,364/1,364 단일 객체 · 배열 0건**(`두두원_회신_발송본.md`) 으로 확인됐다 — **이 항목은 더 이상 열려 있지 않다. 다시 회신을 요구하지 말 것.**

**(역사) 왜 관대 수신이 못 고쳤는가**: `tai`/`ncgi` 의 TAC·셀 ID 를 지어낼 수 없고, `"cell-002"` 에서 올바른 hex 를 유도할 근거가 없으며, `_nodeAddrs` 를 첫 원소만 취해도 되는지 합의가 필요했다. 키 이름(`timeStamp`)은 오탐 위험 때문에 추측 수리 대상에서 의도적으로 제외했다. **결국 5종 전부 두두원이 원천 수정해 해소됐다 — 관대 계층에 추측 수리를 넣지 않은 판단이 옳았다.**

**해소 확인 (2026-09-17 10:07:06~15:22:51 검증 창)** — `13p_d` 341건 수신, 잔존 위반 **0건**.

| # | 항목 | 검증 결과 |
|---|---|---|
| 1 | `timeStamp` 대소문자 | 682/682 정상 파싱. 수신 원문 2,384건 중 소문자 `timestamp` **0건** |
| 2 | `_nodeAddrs` 배열→단일 객체 | 단일 객체 1,364/1,364. 배열 **0건** |
| 3·4 | `tai` / `ncgi` 추가 | 682/682 존재 |
| 5 | `nrCellId` hex 9자리 | `"123456789"` — 규격 위반 **0건** |
| — | `_powerEnergyConsumptionInfos` (키 이름, §6 치명) | 341/341 적재, 배열 원소 682개, `_powerEnergyConsData` 7필드 전수 채워짐 |

**남은 관찰 1 — `nrCellId` 가 gNB 간 중복**: 형식은 합격이나 gNB1·gNB2 가 **같은 `123456789`** 를 보고하고 `mcc`/`mnc` 도 같아 NCGI 기준으로는 두 gNB 가 같은 셀로 식별된다. 지금은 `gNbId`(000001/000002)와 FQDN 으로 구분하므로 제어에 지장은 없으나, **셀 단위 에너지 집계를 넣으면 두 gNB 가 병합된다.** 두두원에 gNB 별 상이한 값을 요청해 뒀다.

**남은 관찰 2 — `_POWER.tmpl`/`_SIGNAL.tmpl` 단독 경로는 회선 미실증**: 세 파일 모두 수정을 확인했으나(mtime 01:45:18 / 01:46:36 / 01:50:02), 실전송은 통합 `13p_d_…v1.0.tmpl` **1종뿐**이다. `ncof_flow_subscription_core.cpp:101-128` `Select_2p_Report_File()` 이 `_RF_SIGNAL`·`_POWER_ENERGY_CONSUMPTION` **둘 다** 있으면 `2p_both` 로 통합본을 고르고, NCOF 는 둘 다 구독하므로 단독 경로가 선택될 일이 없다. 단독 경로가 실제로 쓰이기 시작하면 그때 재검증해야 한다.

**영향**: `13p_d` 는 ~~100% 거절~~ → **전수 통과**한다. 전력·에너지 본문(`_powerEnergyConsData` 7필드)이 실제로 적재된다. 나머지 통지(`8_`, `9_`, `10_a`, `11p_b`, `12p_c`)는 여전히 `-999` 센티넬·정수 필드 소수값 때문에 관대 수신의 수리를 거친다 — 패치 B 를 붙잡고 있는 것이 정확히 그 두 항목이다(§6 표의 `-999` 센티넬 행·정수 필드 소수 행).

> ⚠️ **"원장에 없다 = 안 왔다" 가 아니다.** 관대 계층은 **무오류 통지를 원장·`raw.json` 에 남기지 않는다** — `lenient_ingest.py:358-359` 의 `if report["before_error_count"] == 0: return await self.app(scope, replay, send)` 조기 반환이다. 9/17 에 `13p_d` raw 덤프가 0건이 된 것은 통지가 끊긴 게 아니라 **전수 통과의 증거**였다(9/16 까지는 ricf 덤프만 하루 2,300~4,300건씩 쌓였다). 이 절이나 원장 부재를 근거로 수신 중단을 판단하지 말 것.

### 6.2 하위 구독 응답의 구독 ID — ~~mockup 과의 결정적 차이~~ **수정 요청에서 협의 항목으로 강등 (2026-09-11)**

> 🔻 **이 항목은 이미 2026-09-11 발송 메일에서 "협의 5 (낮음 · 지금 수정 요청 아님)" 으로 강등돼 나갔다**
> (`두두원_수정요청_메일초안.md:12` 우선순위 표, `:27-33` 내부 감사 3번, 발송 본문 `:308-338`).
> 9/17 회신(`두두원_회신_발송본.md`)은 이미 강등된 항목이라 재론하지 않았다. 이유 셋이다.
>
> 1. **NCOF 가 자체 해소했다** (§8 의 8, `e49c613`) — 응답에 ID 가 없으면 요청 본문의 `notifId` 를
>    하위 구독 ID 로 채택한다(`subscription_handler.py:140-165`; 그 앞 `:138-139` 헤더 갈래는 이전부터 있던 것).
>    실장비 해지 **10/10 → 200** 실증(§8).
> 2. **`Subscription-ID` 는 어느 규격에도 없다.** `ncof_yaml` 전체 grep 결과 **0건**이다. 규격이 요구하는 것은
>    `201` + **필수 `Location` 헤더**이고(`Nncof_EventsSubscription_PoC_ETRI_DoDo1.yaml:38-47`, `:243-252`,
>    `TS29591…yaml:44-58`, `TS29508…yaml:43-53`), `Subscription-ID` 는 우리 저장소의 mock NF 3종과
>    NCOF northbound 만 지키는 **로컬 관행**이다. 규격 준수를 명분으로 규격 이탈을 요구하는 꼴이었다.
> 3. **NCOF 자신도 `Location` 을 파싱하지 않는다** — `subscription_handler.py:138-139` 는 `Subscription-ID`
>    헤더만 본다. 우리가 지키지 않는 규약을 상대에게 요구하는 모양이 된다.
>
> 그리고 두두원에는 uuid 발급기가 아예 없어(§7) 이건 신규 기능 개발이다 — PoC 일정 밖이다.

**당시 증상(기록)**: 두두원 응답에는 ID 가 **본문에도 헤더에도 없어** `_send_external_subscription` 이 `None` 을 돌려주고,
당시 `subscription_handler.py:290`(현행 `:330`)의 `if external_sub_id:` 가 레코드를 통째로 버렸다 → `external_subscriptions` 가 `[]`
→ GUI 팬아웃 미표시 · 상태 미저장 · **구독 해지 영구 불가**(고아 구독 누적). `e49c613` 으로 해소됐다.

| NF | 성공 응답 | ID 위치 | 규격(`201`+필수 `Location`) 대비 |
|---|---|---|---|
| mock SMF `:9001` (4건) | 201 | 본문 `subId` **+** `Subscription-ID` 헤더 (`subscriptions_collection_api_impl.py:51,75`) | `Location` 없음 — **우리도 미준수** |
| mock AF/RICF `:9002` (6건) | 201 | **`Subscription-ID` 헤더 전용** (`simulation.py:251`. 본문 주입은 `:232` 에 주석 처리) | `Location` 없음 — **우리도 미준수** |
| NCOF 자신 `:9000` | 201 | `Subscription-ID` 헤더 (`ncof_events_subscriptions_impl.py:52`) | `Location` 없음 — **우리도 미준수** |
| **두두원** | **200** | **없음** | `201`·`Location` 둘 다 없음 |

> 📌 **이건 애초에 순수한 두두원 결함이 아니었다.** 두두원은 요청 본문의 `notifId` 를 자기 `subscription_id` 로 채택하고
> (`ncof_flow_subscription_handlers.cpp:53-54, 353-354, 446-447, 603-604, 681-682` — 2p 는 `:202-212`),
> DELETE 도 `key‖subscription_id‖notif_id` 셋 다 매칭한다(`ncof_flow_subscription_core.cpp:1219`
> — 9/15 개정으로 `:1207`→`:1219` 로 이동. 함수는 `Stop_Ncof_Subscription_By_Id`, `:1202`).
> **즉 NCOF 는 해지에 필요한 값을 이미 스스로 만들어 갖고 있다.**
> 2p 핸들러(`:202`)는 요청의 `subscriptionId` 를 읽는데 **NCOF 는 그걸 보내지 않는다**(`subId` 는 `null` 로만 나감).

> 🔴 **남아 있는 무증상 실패 위험 — 발송 메일에서 두두원에 미리 부탁해 둔 항목이다.**
> 두두원이 식별자 처리를 바꿔 새 ID 를 발급하고 내부 식별자를 `notifId` 로 두면, NCOF 의 DELETE 가 매칭되지 않는다.
> **그런데 NCOF 는 `404` 를 "이미 해지된 구독" 으로 간주해 성공 처리하고 자기 기록까지 지운다.**
> 그러면 NCOF 로그에 실패 흔적이 남지 않고 **두두원 쪽 구독만 살아남아 주기 리포트가 계속 온다** — 양쪽 다 무증상이다.
> 상대에게는 "배포 전에 알려 달라" 고 요청했고, **우리 쪽 `404` 처리도 손보겠다고 약속했다(미이행)**.

**향후 협의 시 제안할 것**: `Subscription-ID` 가 아니라 **규격대로 `201` + `Location: {apiRoot}/…/subscriptions/{subscriptionId}`** 로 양측을 맞춘다.
그러려면 NCOF 수신부에 `Location` 파싱을 추가해야 하고(현재 `Subscription-ID` 만 본다), 참조 구현
`nsmf-server/src/nsmf/impl/subscriptions_collection_api_impl.py:51-52, 73-77` 과 mock NF 3종도 `Location` 을 싣도록 함께 고쳐야 한다.
두두원 쪽에는 `201` 을 반환하는 `handle_subscription_request()` 가 `http2_server.cpp:284-297` 에 이미 작성돼 있으나 호출되지 않는 것으로 보인다.
**우리 쪽 정리가 먼저다 — 그전에 두두원에 요구하면 안 된다.**

---

> ✅ **동반 수정 완료 (2026-09-17 확인).** 위에서 요구했던 §6 요청표 행 교체는 반영돼 있다 —
> 해당 행은 현재 `~~높음~~ **강등 — 수정 요청 아님, 협의 항목**` 으로 시작하며 `Location` 근거와
> 9/17 회신에서 제외한 경위를 싣고 있다. 내부 모순 없음.

### 6.3 규격 원본 감사 (2026-09-10, 2026-09-17 재확인) — 책임 소재 재배분

`/home/labry/git/ncof_yaml`(branch `main`)이 **규격 원본 저장소**다: 최상위 OpenAPI yaml 9종 + 그 생성물
`simplified/` 9종·`callbacks/` 4종 + `ncof_json/` 참조 샘플 26개 파일(API 페이로드 24 + 조회표 2:
`supi_to_guami_info.json`, `supi_to_ip_mapping_info.json`). 그 페이로드 24종 전부를 yaml 스키마에 대조
(교차 파일 `$ref` 전부 해소, Draft7 + `additionalProperties:false` 2회 검사)한 결과 **확정 위반 97건**.
아래는 그중 **책임 소재가 이전 판과 달라지는 것들**이다.

> ⚠️ **9/10 감사는 워킹트리를 봤다 — 커밋 상태와 다르다.** `ncof_yaml` HEAD 는 `a4a0d06`(2026-05-26)에서
> 멈춰 있고, 워킹트리에 **미커밋 수정 4파일**이 9/17 현재도 그대로 남아 있다(`callbacks/Nnef_…Callback….yaml`,
> `simplified/TS29122_CommonData….yaml`, `simplified/TS29571_CommonData….yaml`,
> `simplified/TS29591_Nnef_EventExposure….yaml`). 아래 🔴 절의 판정 하나가 **이것 때문에 틀렸다.**
> 규격 수정은 커밋해서 원본에 반영할 것 — 안 하면 다음 감사가 또 같은 착시에 빠진다.

#### ⚠️ 두두원이 맞고 우리 샘플이 틀린 것 — 두두원 목록에서 빼라

| 항목 | 실상 |
|---|---|
| `serviveName` | **규격 그대로**다(§4 📌). 오타 아님 |
| `notifMethod` | NEF 구독 5종(`4_`,`4p_`,`5_`,`5p_`,`6p_`)에서 **우리 샘플이 `notificationMethod` 로 잘못 씀**. 규격은 `notifMethod`(`SupplementaryData#ReportingInformation`). `notificationMethod` 는 Nncof API 이름이 NEF 에 섞여 든 것. 두두원 수신부는 규격대로 `notifMethod` 를 읽는다(`http2_server.cpp:286`) → **우리가 보내는 값이 빈 값으로 떨어진다** |
| `dlPeakThroughput` | **규격이 틀렸다.** 규격은 `dlPeakThroughPut`(대문자 P)인데 형제 `ulPeakThroughput` 은 정상 표기. 3GPP verbatim import 잔재이고 우리 샘플·두두원이 독립적으로 둘 다 `dlPeakThroughput` 을 쓴다 → **회선이 이미 합의됐으니 규격을 고쳐라** |
| `PEF_FLOW` | 이 그룹 어디에도 없다. 전부 `PER_FLOW` 이고 정상값이다(§7 의 기존 반증과 일치) |

#### 🔴 규격 자체 버그 — 어떤 페이로드도 만족 불가

`TS29591:891-893` `_PowerEnergyConsumptionInfo.required = [_timestamp, **_PowerEnergyConsData**]` — 대문자 `_P`.
실제 프로퍼티는 `_powerEnergyConsData`(`:889`). 생성된 `callbacks/` yaml 에도 이미 박혀 있다.
형제 `_RfSignalInfo.required` 는 정상이라 단순 오타다. **규격 수정 필수.**

#### ⛔ 일방 수정 금지 — 두두원이 같이 깨진다

**`validityTimes` 위치.** 우리 샘플은 `eventSubs[].upfEvents[]` 레벨에 두는데 규격은
`skipReportingInstruction.validityTimes`(`TS29564:741`)다. 두두원 수신부가 **샘플의 잘못된 위치를 읽는다**
(`ncof_flow_subscription_core.cpp:496`, `:641`, `:696`). 규격대로 옮기면 두두원의 UPF 구독 시간창 검증이
조용히 깨져 `subscription time not found` → 0 을 반환한다. **동시 수정으로 조율할 것.**

#### 우리 샘플의 하드 위반 (strict validator 가 오늘 거절)

| 샘플 | 위반 |
|---|---|
| `14_e` | `qosPolAssistSets[0..3]` 이 `appId` 와 `fDescs` 를 **둘 다** 담아 `oneOf` 위반 ×4 — **가려지지 않은 실제 거절**. 앱 단위/플로우 단위 정책이 구조적으로 판별 불가 |
| `11p_b` | `dispersionInfos[]` 가 `gpsi`+`supi`+`ueAddr` 셋 다 → `oneOf`(정확히 하나) 위반 |
| NSMF 4종 | `qosMonPending: false` → `enum: [true]` 위반. 3GPP 응답 전용/true 전용 플래그는 **생략**이 정답 |
| `7_`, `7p_` | `inclRatType: false` → 동일 |
| `2p_` | `eventsSubs[0].eventFilter` 에 required `tgtUe` 없음 |
| `14_e` | `anaMetaInfo.nfIds` 가 UUID 형식 위반 (`upf-uuid-001` 등, `NfInstanceId` format uuid) |
| `13p_d` | 이벤트 항목 키가 `timestamp`(소문자 s) ×2(`:7`, `:133`). `NefEventNotification`(`simplified/TS29591…:314`)은 `timeStamp`(`:320`)가 **required**(`:427-429`) → **키 드롭 + required 누락** 동시 발생. `ncof_json/` 25종 중 소문자 `timestamp` 를 쓰는 파일은 **13p_d 하나뿐**이다(형제 9종 `8_`,`8p_`,`9_`,`9p_`,`10_a`,`10p_a`,`11p_b`,`12_c`,`12p_c` 전부 `timeStamp`) |
| `13p_d` | `ncgi.nrCellId` 가 `"cell-001"`/`"cell-002"` ×4(`:36`, `:95`, `:157`, `:203`) — `NrCellId` 패턴 `^[A-Fa-f0-9]{9}$`(`simplified/TS29571…:991-993`) 위반. `Ncgi.required` 에 들어 있고 enum 처럼 `anyOf` 로 빠져나갈 구멍도 없어 **확정 거절**이다. `ncof_json/` 에서 `nrCellId` 를 담은 파일도 13p_d 뿐 |
| `13p_d` | `_powerEnergyConsumptionInfos` 항목 2건이 위 🔴 **규격 자체 버그**(`_PowerEnergyConsData` required)에 걸린다. 샘플은 정상 표기 `_powerEnergyConsData` 를 쓰므로 **규격을 고쳐야 풀린다** — 샘플 단독 수정 금지 |

> 📌 **위 `13p_d` 3행은 이 표에만 없었을 뿐 문서에 없던 사실은 아니다.** `timeStamp`/`nrCellId` 는 §6.4 메일 초안 경고와 "NCOF 측 정리" 4-③ 에 이미 적혀 있다. 여기 다시 싣는 이유는 §6.3 이 **"우리 샘플의 하드 위반" 전수 목록** 노릇을 하기 때문이다. 9/10 감사가 이 표에서 왜 빠뜨렸는지는 기록이 없다 — 표 머리말이 "책임 소재가 이전 판과 달라지는 것들" 로 범위를 좁혀 둔 탓으로 보이나 **확정 불가**.
>
> ⚠️ **9/17 기준, 뒤처진 쪽은 우리다.** 두두원은 9/17 재빌드에서 `timestamp`→`timeStamp` 와 `nrCellId` hex 9자리를 **이미 고쳤고** 13p_d 341건 실측 잔존 위반 0건이다(§6.1 해소됨 참조). `ncof_json/13p_d_….json` 은 **아직 둘 다 위반 중**이라 회선의 정본이 두두원 쪽으로 넘어갔다 → "NCOF 측 정리" 4-③ 을 실행해 우리 샘플을 맞춰라.
> 단, 두두원은 gNB1·gNB2 가 **똑같이 `123456789`** 를 보고한다 — 형식은 합격이나 NCGI 상 동일 셀로 식별된다. 우리 샘플의 `cell-001`/`cell-002` 를 hex 로 바꿀 때는 **셀별로 다른 값**을 써서 이 결함을 따라가지 말 것.
> 반대로 두두원에 요청했던 `_nodeAddrs`(배열→단일 객체, `ncof_yaml` `26057fa`)와 `tai`/`ncgi` 추가(`a4a0d06`)는 **우리 샘플이 이미 맞다**(둘 다 2026-05-26 반영분).

#### 조용히 드롭되는 키 이름 드리프트 (11건) — 오류가 안 나서 가장 위험

`notifMethod`, `nsiIds`(스칼라→배열도), `intGroupIds`/`interGroupIds`, `anyUeId`, `requestedQoe`,
`ssIds`/`bssIds`, `predQoeVariance`. 규격이 `additionalProperties:false` 를 안 걸어서 정합 소비자가
**알림 방식·슬라이스 id·그룹 필터·QoE 목표·SSID 필터를 전부 조용히 버린다.**

> 🔴 **가려진 복합 결함:** `intGroupId` 키를 고치면 그 값 `"group-id-001"`/`"group-id-002"` 가 이번엔
> `GroupId` 패턴(`TS29571:1071`) 위반으로 걸린다. **드롭 5건이 400 5건으로 바뀐다** — 키와 값을 반드시 같이 고쳐라.

#### 그 밖에

- **`_minDelayDl` 은 어느 규격 파일에도 없다**(`9_`,`9p_`,`10_a`,`10p_a`). `PerformanceData` 는
  `_minRtt,_maxRtt,_delayUl,_minDelayUl,_maxDelayUl,_jitter` 를 정의하고, 샘플은 규격의 `_maxDelayUl` 을
  한 번도 안 쓴다 → `_maxDelayUl` 의 복사·개명 실수로 보인다. 생성 모델이 측정된 DL 지연을 조용히 버린다.
- `11p_b` `dispersionInfos[]` 의 `ipTrafficFilter` 는 `DispersionCollection` 에 없는 프로퍼티다.
  거기의 플로우 필터는 `flowDesp`(**문자열**)다.
- **파일명 오류 2건:** `13p_d` 는 이름과 달리 **NEF-shaped** 다(`NncofEventsSubscriptionNotification` 은
  `eventNotifications` 를 쓰고 `subscriptionId` 가 required). 두두원도 NEF-shaped 로 보내므로 **이름만 틀렸다.**
  `2p_` 도 실제로는 `NefEventExposureSubsc` 이고 `5p_` 와 거의 중복이다.
- `8_`/`12p_c` 계열 **샘플은 깨끗하다** — 단위 접미사 214개 전부 패턴 일치, 센티넬 0건, 정수 필드 소수 0건.
  즉 §6 의 단위·센티넬·소수 항목은 **전적으로 두두원 렌더링 단계의 문제**다(위 토큰표 회귀 참조).
- `defaultQoSFlowInd` → 규격은 `defaultQosFlowInd`(`TS29564:542`). 3GPP JSON 관례가 `Qos` 라 **샘플·두두원 양쪽이 틀렸다.**
- `10_a` 와 `10p_a` 는 바이트 단위로 동일하다.
- enum 위반은 이 규격에서 **구조적으로 검출 불가**다 — `NefEvent`, `_RefSignalType`, `_BlockType`,
  `_ConnectivityType`, `_CellPowerState`, `RatType` 이 모두 `anyOf: [enum, type:string]` 이라 아무 문자열이나 통과한다.
- **미커밋 규격 수정이 새 위반 하나를 깨운다.** 워킹트리의 `simplified/TS29122_CommonData….yaml` 이
  `Mcc` 에 `pattern: ^\d{3}$`, `Mnc` 에 `pattern: ^\d{2,3}$` 를 새로 건다(HEAD 에는 description 만 있고
  패턴이 없다). 이걸 커밋하는 순간 `2p_` 의 `"mcc": "01"` ×2(`:23`, `:34`)가 **조용한 통과에서 패턴 위반으로
  승격**된다. 나머지 샘플의 `mcc` 는 `001`/`000`/`999`, `mnc` 는 `001`/`999` 라 안전하다.
  **규격 커밋과 `2p_` 수정을 같은 커밋으로 낼 것.**

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
| 두두원 `send_json/` 을 보면 제어 수신 여부를 알 수 있다 | ❌ `send_json/` 은 **송신 덤프 전용**이다. 수신 제어의 부수효과는 메시지별로 갈린다 — `14_e` 는 MySQL INSERT(`Save_14e_Ncof_To_Pcf_By_Config`, `ncof_flow_control.cpp:123`) + **2026-09-15 신설 경로**로 UE 4개(`upf_qos_udp.h:6` `QOS_APPLY_UE_COUNT`)가 다 차면 실장비 UPF 로 바이너리 UDP 발사(`ncof_flow_control.cpp:332-336` → `upf_qos_udp.cpp:9`), `15f` 는 MySQL INSERT 2건 + gNB2 SSH 셸아웃(§5). **셋 다 `send_json/` 에 아무 흔적을 남기지 않는다.** 관측 경로는 MySQL 직접 조회(읽기 전용 제약으로 우리는 불가)와 두두원 앱 stderr 뿐이고, stderr 는 `tee ~/SBI/app/sbi_poc_app.<날짜>.log` 로 기동하기 시작한 2026-09-17 이후에만 사후 확인이 된다 |
| `13p_d` 와 `8_`/`9_`/`10_a` 는 별개 스케줄러로 나간다 | ❌ 단일 `Ncof_Subscription_Report_Thread`(`ncof_flow_subscription_core.cpp:905-984`) 1초 폴링이 전부 처리 |
| `serviveName` 은 양측이 공유하는 오타다 | ❌ **규격 그대로다.** `TS29508…yaml:391` 이 그렇게 선언하고 description 에 명시. `serviceName` 으로 고치면 깨진다(§6.3) |
| `_nodeAddrs` 는 배열이 맞다 | ❌ **객체가 맞다.** `ncof_yaml` 커밋 `26057fa`(2026-05-26) "fix _nodeAddrs array to object" 로 확정. 배열로 보이는 파일은 5/4 자 worktree 스냅샷이다 |
| `notificationMethod` 는 NEF 구독에서도 맞는 이름이다 | ❌ NEF 는 `notifMethod` 다. 두두원이 규격대로 읽고 우리 샘플이 틀렸다(§6.3) |
| 단위 없는 정수·센티넬은 규격 샘플에도 있다 | ❌ `8_`/`12p_c` 샘플은 깨끗하다(단위 214개 전부 일치, 센티넬 0건). 두두원 렌더링 단계의 토큰표 회귀다(§6.3). **단위 접미사는 9/17 빌드에서 해소**(`ncof_flow_report_common.cpp` 토큰표가 `Json_Quote("50000000 bps")` 로 복구), **센티넬 `-999` 는 미해소** — 패치 B 회수를 막는 원인 ① 이다 |
| 두두원이 uuid4 로 구독 ID 를 발급한다(발급만 안 실어 준다) | ❌ **발급기 자체가 없다.** `src/`+`include/` 전체에 uuid·random 생성 코드 0건(`uuid_generate`·`boost/uuid`·`random_device`·`mt19937`·`rand()` 전부 0). `uuid` 가 걸리는 8곳은 전부 하드코딩 리터럴(`ncof_flow_report_common.cpp:740-743` — 9/17 재빌드로 `:458-461` 에서 밀렸다, `ncof_send_templates.cpp:207,254-255,271` → `pcf-uuid-001` 등). 두두원 자신의 구독도 `notifCorrId` 하드코딩(`NOTIFICATION_2026-03-01T12:00:00+09:00_1` — `1_`/`1p_` 템플릿이 같은 `__NOTIF_CORR_ID__` 기본값을 쓴다)이고 PCF·RICF 가 같은 값이다 → §6.2 의 `Subscription-ID` 헤더 요청은 **신규 기능 개발**이다. 게다가 그 헤더는 **어느 규격에도 없다** — `ncof_yaml` 전체(`*.yaml`·`callbacks/`·`simplified/`)에 `Subscription-ID` **0건**이고, 규격이 요구하는 것은 `201` + `Location` 헤더다(`TS29591_Nnef_EventExposure_PoC_ETRI_DoDo1.yaml:45-58`, `required: true`). §6.2 의 "가장 작은 수정" 문구(400행)와 어긋나므로 함께 고칠 것 |
| 해지 URL 의 `:`/`+` 는 percent-encoding 해야 안전하다 | ❌ **인코딩하면 두두원 해지가 깨진다.** httpx 0.28.1 → Starlette ASGI 왕복 실측: 그대로 보내면 마지막 경로 세그먼트가 notifId 와 바이트 일치, `quote(safe='')` 를 씌우면 `%3A` 가 남는다. FastAPI 는 복호하지만 두두원은 원문 그대로 잘라 비교하므로(`ncof_flow_subscription_core.cpp:1112-1137`) 404 로 조용히 실패한다. `:`/`+` 는 RFC 3986 경로 세그먼트 허용 문자다 |
| `main.py:88` 은 주석만 해제하면 된다 | ❌ **알려진 기동 실패가 되살아난다.** 복원은 구독 1건당 수 초가 걸리고 `lifespan` 안에서 await 하면 hypercorn 기동 타임아웃(60초)에 걸려 **구독 12건에서 기동 실패**(실측). 게다가 notifId 폴백이 들어가면 Phase 2 연출 대기가 구독당 4~6초로 늘어 더 빨리 걸린다 → 백그라운드 태스크로 분리해야 한다 |
| 원장(`ledger.jsonl`)에 없으면 그 통지는 안 온 것이다 | ❌ **관대 계층은 무오류 통지를 아예 기록하지 않는다.** `lenient_ingest.py:358-359` 가 `before_error_count == 0` 이면 `_log_report`·`_persist`(`:361-362`) 를 건너뛰고 조기 반환한다 → 원장에도 raw 덤프에도 안 남는다. `powerEnergy` 를 담은 raw 덤프는 9/15 **1,434건** → 9/16 **770건** → 9/17 **0건**인데, 이건 미수신이 아니라 **전수 통과의 증거**였다(9/17 13p_d 341건 수신, 잔존 위반 0건). "원장에 없다 = 안 왔다" 로 읽지 마라 |
| 그렇다면 raw 덤프 0건은 언제나 전수 통과다 | ❌ **트래픽이 0이어서 0일 수도 있다. 앞 행과 구분할 판별자가 필요하다.** 판별자는 `logs/app.log` 다 — 두두원 앱이 정지한 9/17 16~19시에도 NCOF 는 시간당 **1,440행**(분석 루프)을 계속 찍었지만 통지 관련 행은 **0건**이다(마지막 통지 `15:23:01` RICF, 갭 이후 첫 수신 `20:27:54` PCF). **raw 덤프 0건은 반드시 `app.log` 의 수신 건수와 대조해서 읽어라** — 덤프만 보면 "전수 통과" 와 "앱 정지" 가 똑같이 0으로 보인다 |
| 두두원이 요청 2(키 이름)를 고치면 우리 규격의 `_PowerEnergyConsData` required 오타 때문에 오히려 422 로 악화된다 | ❌ **오타가 생성 모델에 전파되지 않았다.** 규격은 프로퍼티를 `_powerEnergyConsData` 로 두고(`TS29591…yaml:889`, `callbacks/Nnef…yaml:2892`) required 에는 대문자 `_PowerEnergyConsData` 를 적어 놨지만(`:891-893`, `:2894-2896`), openapi-generator 가 프로퍼티에 없는 required 항목을 버려 생성 모델의 필수는 `_timestamp` 하나뿐이고 `power_energy_cons_data` 는 `Optional[...] = None` 이다(`nnef-server/src/nnef/models/power_energy_consumption_info.py:41,50`). 실측으로도 9/17 13p_d 341건 전수 통과. **규격 오타 자체는 여전히 고쳐야 하지만 차단성은 아니다** |
| `Subscription-ID` 응답 헤더를 요청하는 것이 규격 준수다 | ❌ **어느 규격에도 없는 헤더다.** `ncof_yaml` 의 `*.yaml`·`callbacks/*.yaml`·`simplified/*.yaml` 전체에 `Subscription-ID` **0건**이고, 규격이 요구하는 것은 `201` + **`required: true` 인 `Location` 헤더**다(`TS29591…yaml:45-58`). 게다가 NCOF 는 `Location` 을 파싱조차 하지 않고(`subscription_handler.py:133-139` 는 본문 `subscriptionId`/`subId` → `Subscription-ID` 헤더 순으로만 본다), NCOF 자신의 201 응답도 `Location` 없이 `Subscription-ID` 만 싣는다(`ncof_events_subscriptions_impl.py:50-54`). **양쪽 다 규격 위반**이다 → 위 uuid 행과 함께 **§6.2 의 "요청 사항" 문안을 `201` + `Location` 으로 고칠 것** |
| 패치 A(`_DODO1_NO_FRACTIONAL_SECONDS`)를 끄면 소수 초 제거만 풀린다 | ❌ **`startTime` 60초 백데이트까지 같이 풀렸다.** 플래그 하나가 무관한 두 완화를 묶고 있어, 그대로 뒤집었다면 회수 실패 시 원인이 소수 초인지 시계 오차인지 구분 불가였다. `ce71818` 에서 백데이트를 `if` 밖으로 빼 **무조건 적용**으로 분리한 뒤 플래그만 `False` 로 내렸다(`subscription_request_builder.py:89`, `:109-115`). 회귀 시험 `tests/test_target_period.py` 4건 |
| 요청 3(단위 접미사)이 반영되면 스루풋 필드 위반이 사라진다 | ❌ **8p 주기보고 경로(682건)는 스루풋 8필드가 100% `"-999"`** 라 토큰표 수정과 무관하다. 센티넬은 별도 함수에서 나온다(`ncof_flow_targeting.cpp:21-28` `Json_Stamp_Number_Default()`, `ncof_flow_report_common.cpp:345,363,382`) |
| 센티넬 `-999`(원인 ①)만 먼저 고치면 그만큼 422 가 줄어든다 | ❌ **오히려 늘 수 있다.** `-999` 에 가려져 있던 AF PERF_DATA 682건이 원인 ②(정수 필드 소수값)로 드러나 영향 통지가 최대 2,045건까지 늘어난다. ①·②는 **반드시 동시 수정**이어야 패치 B 를 회수할 수 있다 |
| 패치 B 는 전부냐 전무냐다 | ❌ **`value_error` 갈래는 지금 잘라도 된다.** `_candidates()`(`lenient_ingest.py:110`)의 `value_error` 갈래(`:134-142`, `RETRY_*`/`STRIP_UNIT`)는 원장 **78,023건 전수에서 0회**다. 단 **`string_type` 갈래(`:123-132`)는 자르지 마라** — 보관 원장 `ledger.jsonl.upto-20260917-202439`(77,904건)에 `STRINGIFY_VOLUME_BYTES` 154,664 / `STRINGIFY_PACKETRATE_PPS` 120,664 / `STRINGIFY_BITRATE_BPS` 90,498 = **365,826회** 찍혀 있고, 0회가 된 것은 두두원이 요청 3 을 고친 **9/17 20:24 이후 119건 구간뿐**이다. 두두원이 토큰표를 되돌리면 그대로 422 가 된다. 남길 것은 `_drop_sentinels()`(`:82`) + `int_type` 갈래(`:115-121`) + `string_type` 갈래이고, 전량 회수만 ①·② 동시 수정에 묶여 있다 |
| 두두원이 우리 14_e 제어를 받으면 DB 와 gNB2 SSH 로만 흘러간다 | ❌ **14_e 경로는 9/15 부터 실장비 UPF 로 바이너리 UDP 도 발사한다.** 신규 모듈 `upf_qos_udp.{h,cpp}`(9/15 04:20 / 22:57) + `ncof_flow_control.cpp:332-336` `Send_Qos_Apply_To_Upf_Udp(config.upf_ip, config.upf_port, packet)`. UE 4개(`QOS_APPLY_UE_COUNT`, `upf_qos_udp.h:6`)가 다 차야 발사되고 **NCOF 에 이 경로 가시성은 0** 이다. → 위 `send_json/` 행의 "수신 제어는 MySQL 로만 간다" 는 **14_e 에 한해 부정확**해졌다(다만 UDP 도 `send_json/` 에는 안 남으므로 그 행의 결론은 유지). **§5 의 15F(cell power) 경로 서술은 그대로 유효하다** — UDP 는 14_e 전용이다 |
| `nrCellId` 가 규격 형식(hex 9자리)만 맞으면 gNB 구분이 된다 | ❌ **gNB1·gNB2 가 같은 `123456789`** 를 보고한다. 형식은 합격이지만 NCGI 상 **동일 셀**로 식별된다. 셀 단위 분석·제어를 하려면 gNB 별로 다른 `nrCellId` 를 두두원에 요청해야 한다 |
| 구독 트리 중복은 §8.1 의 이론상 우려다 | ❌ **9/17 오전에 실제로 터졌고, §8.1 이 적은 것보다 나빴다.** §8.1 은 재기동 1회 기준 **2배**(상향 2→4건)를 든다. 그런데 두두원이 10:02:57 / 10:05:01 / 10:20:18 **3회** 재기동하며 매번 구독을 재전송해 **4배**가 됐다 — 상향 8 / external 40 / 간선 72(정상치 2 / 10 / 18). **중복 배수는 두두원 재기동 횟수 + 1 이다.** 9/17 20:24 §8.1 의 "청소 후 재기동" 으로 2 / 10 / 18 복구 |
| 두두원 앱의 9/17 15:23:01 정지는 크래시다 | ❌ **크래시는 배제됐다** — 코어덤프 0건, OOM 킬 0건, 메모리 26Gi 여유. 다만 앱 로그가 없어 정지 원인 자체는 **UNVERIFIABLE**(정황상 4분 전 SSH 로그인 → 운영자 정지). 이후 `tee ~/SBI/app/sbi_poc_app.<날짜>.log` 로 기동하도록 요청했다 |
| `_POWER.tmpl`/`_SIGNAL.tmpl` 단독 경로도 회선에서 검증됐다 | ❌ **미실증이다.** 실제 전송된 것은 통합 `13p_d_…v1.0.tmpl` 1종뿐이다. 단독 템플릿 2종은 소스에만 있고 회선 실측 근거가 없으니 "3종 모두 통과" 로 말하지 마라 |
> §3 의 `Detect_Ncof_Recv_Json_Type()` 인용과 "`(void)path;` 로 경로를 폐기한다" 는 서술은
> **2026-09-10 에 정정됐다**(§3 의 📌 참조). 14/15F 분기 누락과, 5/5p 분기만은 경로를 읽는다는 점.
>
> §5 의 "제어 종착지는 DB INSERT 2건 + gNB2 SSH" 와 §6.2 의 "`Subscription-ID` 응답 헤더를 요청한다" 는
> **2026-09-17 에 정정됐다** — 전자는 9/15 신규 `upf_qos_udp` 모듈로 UPF 행 UDP 갈래가 추가됐고,
> 후자는 규격이 요구하는 것이 `201` + `Location` 이지 `Subscription-ID` 가 아니다. 위 표의 해당 행 참조.

---

## 8. 다음 할 일

**차단성 블로커는 없다.** 제어 루프는 관통됐고, 남은 것은 답신 대기·검증·정리다.

### ✅ 두두원 메일 왕복 — 1라운드 회신 완료 · 2라운드 답신 대기 (2026-09-17)

| 문서 | 상태 |
|---|---|
| `두두원_수정요청_메일초안.md` (`62170fc` → 감사 반영 `ba8c7d4`) | **발송 완료.** 요청 4건 + 협의 1건 |
| `두두원_검증결과_회신초안.md` (`ba8c7d4`) | 9/17 검증 결과의 내부 초안 |
| `두두원_회신_발송본.md` (**미커밋**, 9/17 20:36) | **발송 완료.** 실제로 나간 본문 |

> 📌 이 절의 옛 서술 "4건 구성 — ① 소수 초 ② 키 ③ 단위 ④ **구독 응답 ID**" 는 **오기였다.**
> 9/11 감사에서 구독 ID 는 **협의 5(요청 아님)** 로 내려가고, 그 자리에 **요청 4 = 제어 결과 확인 수단**이
> 신설됐다(`두두원_수정요청_메일초안.md:27`, `:37`). 아래 표가 발송본 기준이다.

**두두원이 요청 1~3 을 전부 반영했다** — 소스 수정 9/17 01:43~01:57, 바이너리 재빌드 9/17 10:02.

| 요청 | 결과 |
|---|---|
| ① ISO8601 소수 초 | ✅ 파서가 `sscanf(…"%d-%d-%dT%d:%d:%lf%c%d:%d"…)` + `sec=(int)sec_d` 로 수정됨(`ncof_flow_subscription_core.cpp:228`). 회선 실증까지 끝나 **패치 A 회수**(`ce71818`) |
| ② `13p_d` 키·구조 4종 | ✅ 341건 수신, 잔존 위반 **0건**. 이전엔 940건 전량 422 였다 |
| ③ 단위 접미사 | ✅ **단, 적용 범위 한정.** `12p_c` 경로 678건은 규격 적합. `8p` 주기보고 682건은 스루풋 8필드가 100% `"-999"` 라 이번 수정과 애초에 무관하다 → 후속 요청 ① 로 넘어갔다 |
| ④ 제어 결과 확인 수단 | ⏳ **미응답.** 4지선다(stderr 공유 / 수신 덤프 / 실패 시 `500` / `_powerState` 에코) 중 아무것도 반영·회신이 없고, 우리 회신에서도 다시 걸지 않았다. **아래 "남은 검증 1건" 이 안 닫히는 이유가 이것이다** |
| 협의 5 구독 응답 ID | 🟡 **수정 요청 아님 · 감시 대상.** NCOF 가 `notifId` 폴백으로 자체 해소했다. 다만 두두원이 식별자 처리를 바꾸면 우리 DELETE 가 매칭되지 않고, **NCOF 는 `404` 를 "이미 해지됨" 으로 보아 성공 처리하고 자기 기록만 지운다** → 두두원 구독만 살아남아 리포트가 계속 온다. 사전 통보를 요청해 뒀고, **우리 쪽 `404` 처리 보완은 아직 미이행**이다(아래 정리 목록에 넣을 것) |

회신에서 새로 건 것은 **후속 요청 2건**(`-999` 센티넬 · 정수 필드 소수값 — 패치 B 회수의 전제),
**확인 요청 2건**(`upf_qos_udp` 활성화 여부 / 9/17 15:23 앱 종료 원인), **협조 요청 1건**(재기동 사전 공유)이고
**미응답 상태인 요청 4 까지 포함해 전부 두두원 답신 대기 중**이다.

> 🔴 **답신이 와도 바로 패치 B 를 끄지 마라.** `-999` 와 정수 필드 소수값은 **동시 수정**을 요청했다.
> ①만 반영되면 `-999` 에 가려져 있던 AF `PERF_DATA` 682건이 소수값 위반으로 새로 드러나
> 영향 통지가 최대 2,045건까지 **오히려 늘어난다.** 근거는 `두두원_회신_발송본.md` §2 와
> `logs/lenient_ingest/ledger.jsonl`.

> ⚠️ **책임 소재가 역전됐다.** `timeStamp` 오타와 `nrCellId` 형식은 두두원이 9/17 에 고쳤고
> (`"123456789"`, hex 9자리), 이제 **우리 규격 샘플만 위반 중**이다 — `ncof_yaml`(HEAD `a4a0d06`)
> `ncof_json/13p_d_….json:7`·`:133` 이 아직 `"timestamp"`, `:36`·`:95`·`:157`·`:203` 이 아직
> `"cell-001"`/`"cell-002"` 다. 아래 정리 4-③ 이 바로 이 항목이니 **우선순위를 올려라.**
> §6.3 "우리 샘플의 하드 위반" 표에도 이 2건이 빠져 있다.

근거 데이터는 `logs/lenient_ingest/ledger.jsonl`, 실제 제어 본문은 `captured/1{4_e,5_f}_control_*.json`.

**임시 패치 회수 현황:** A(소수 초) ✅ **완료** (`ce71818` — 플래그 `False`, 60초 백데이트는 무조건 적용으로 분리) · B(관대 수신) ⏳ **두두원 답신 대기** · C(URI 치환) ✅ 완료

> 📌 아래 "NCOF 측 정리" 5번(소수 초 파싱이 고쳐지면 패치 A 되돌리기)은 이 항목으로 **완료**됐다 —
> 6번·8번처럼 취소선 처리할 것.

### ✅ mock 코어 정합성 — 변경 후 회귀 없음 (2026-09-12 실기동)

`e49c613`(notifId 폴백 + 저장 구독 복원 재개)이 mock 경로를 깨지 않는지 실기동으로 확인했다.
`MODE` 미설정(= mockup NF 테이블) · `NCOF_LENIENT_INGEST` 미설정(정상 경로) · `NCOF_STATE_FILE` 을
스크래치로 분리해 DEVICE 상태 파일과 격리한 뒤, nsmf `:9001` · nnef `:9002` · callback(PCF) `:9004` ·
NCOF `:9000` 을 띄우고 `api-clients` 와 동일한 구독 2건을 POST 했다.

| 검증 항목 | 결과 |
|---|---|
| 구독 2건 POST | 201 + `Subscription-ID` 헤더 |
| 팬아웃 | 10건 (AF 3 · RICF 3 · SMF 4) — DEVICE 모드와 동일 분포 |
| **notifId 폴백 발동** | **0건** (`ID 를 획득하지 못함` 도 0건) |
| `external_subscriptions` | 10건 전부 mock 발급 uuid4. `NOTIFICATION_*` 0건 |
| 통지 수신 | **422 0건** — 관대 수신을 끈 상태에서도 위반 0 |
| 제어 | PCF 1 · RICF 1, 실패 0 |
| 복원 재기동 | 복구 2건 · 낡은 하위 구독 **DELETE 10/10 → 200** · 404 0 · 실패 0 · 재구독 10건 · 폴백 0건 |
| northbound 해지 | `DELETE /subscriptions/{id}` → 200, 핸들러 2→1, 하위 4건 연쇄 DELETE 전부 200 |

**핵심: 폴백은 mock 상대로 한 번도 발동하지 않는다.** mock 3종이 성공 경로에서 항상 uuid4 를
`Subscription-ID` 헤더에 싣기 때문이다(§6.2 표). 정적 분석의 "mock 에는 도달하지 않는 dead code"
판단이 런타임으로 확인됐다. 복원·해지 경로도 mock 상대로 전부 200 이다.

덤으로 확인된 것 셋:

- **mock 페이로드는 실제로 깨끗하다.** 관대 수신을 끈 채로 422 가 0건이다 — §6.3 의 "단위·센티넬
  문제는 전적으로 두두원 렌더링 단계" 라는 결론이 런타임으로 재확인됐다.
- **mock 에서는 제어 수신을 관측할 수 있다.** callback-server 가 받은 제어를 파싱해 로그로 남긴다
  (`GBR_DL: 1000.0 Mbps, MBR_DL: 1000.0 Mbps`). 두두원에는 없는 능력이며(§6 "제어 명령 수용 결과를
  관측할 방법이 없다"), 아래 "남은 검증" 2경로 중 **"NCOF 가 만든 제어 본문이 수신 측에서 의도대로
  파싱되는가" 까지는 mock 으로 증명할 수 있다.** 남는 미지수는 두두원의 실장비 발사부뿐이다.
- **mock 은 메트릭이 실제로 변한다** (`21.0` ↔ `577.0` — `TH_MBPS=500` 경계를 넘나든다). DEVICE 모드는
  템플릿 상수라 `0.0`/`150.0` 두 값뿐이다(§5). 따라서 **emit-on-change 와 제어 desync(아래 정리 1번)를
  재현·검증하려면 mock 이 사실상 유일한 환경이다.**

이번 실행이 덮지 않은 것: 만료 구독 해지 분기(`monDur` 이 2030 이라 미발동 — 단위 테스트만),
복원 중 동시 저장(`_pending_restore` — 단위 테스트만), 중복 구독 시나리오, 장시간 안정성(약 10분),
GUI 화면(API 응답만 확인).

### 남은 검증 — 실장비 반영을 우리는 못 본다 (경로 **2개**)

이번 실측이 보장하는 것은 **두두원이 제어 명령을 파싱·라우팅·기록했다(HTTP 200)** 까지다.
그 뒤 실장비로 나가는 경로가 **둘** 있고, 둘 다 NCOF 가시성이 0 이다.

| 경로 | 무엇 | 발사 조건 | NCOF 가 볼 수 있는 것 |
|---|---|---|---|
| 15f → gNB2 SSH | `gnb_ssh_control.cpp:109` 의 `sshpass … ssh`, `:156`/`:160` 의 `eu.gnbControl.py cell-stop`/`cell-start` | `gNBValue` 가 정확히 `"000002"` — NCOF 페이로드는 만족 | 없음. SSH 가 실패해도 로그만 남고 HTTP 는 200 |
| **14_e → UPF UDP** (2026-09-15 신설) | `ncof_flow_control.cpp:334` 의 `Send_Qos_Apply_To_Upf_Udp(config.upf_ip, config.upf_port, packet)` → `config/6g.config` 의 `UPF_IP=192.168.1.182` `UPF_PORT=5555` 로 바이너리 UDP | `udp_fill_count == QOS_APPLY_UE_COUNT`(=4, `upf_qos_udp.h:6`). 우리 14_e 는 `qosPolAssistSets` 4건을 보내고 SUPI 벡터는 항상 4칸이라(`ncof_flow_report_db.cpp:190`) 인덱스 검사에는 안 걸린다 — **충족될 것으로 보이나 미실증** | 없음. 전송 실패도 `log_message`(`:336`) 뿐이고 응답은 `set_count` 기반 200 |

두두원 stderr 는 파일로 안 남고, gNB2·UPF 호스트 접근은 이번 작업의 읽기 전용 제약에 걸린다.
확인하려면 셋 중 하나가 필요하다:

1. 두두원 담당자가 stderr 에서 `gnb_ssh_control` / `14_e QOS UE…` / `QOS UDP send Complete` 로그를 확인해 주거나,
2. gNB2 호스트(`root@<gnb2_ip>`)·UPF(`192.168.1.182`)에서 상태를 직접 관측하거나,
3. 두두원이 **실패 시 SBI 응답을 500 으로** 내려 주거나 (`두두원_검증결과_회신초안.md` §3-① 에서 요청해 둔 항목).

> 📌 9/17 회신(`두두원_검증결과_회신초안.md` §3-②)에서
> `./sbi_poc_app 2>&1 | tee ~/SBI/app/sbi_poc_app.$(date +%F_%H%M).log` 로 기동해 달라고 요청했다.
> 두두원이 이대로 띄우면 **1번 경로가 처음으로 열린다.**
> 재기동 뒤 `ssh dodo1 'ls -la ~/SBI/app/*.log'` 로 먼저 확인할 것 — 2026-09-17 21:02 현재는 0건이다(실측).

> ⚠️ **14_e 경로에는 단위가 실리지 않는다.** `gbrDl: "5.0 Mbps"` 를 `std::stod`(`ncof_flow_control.cpp:87-88`)
> 가 접미사째 버려 `5.0` 으로 만들고, 그 double 이 그대로 UDP 패킷에 박힌다
> (`:157-158`, `upf_qos_udp.h:10-11` 의 `double gbr_dl`/`mbr_dl`).
> 실장비 UPF 가 이 `5.0` 을 무슨 단위로 읽는지는 **미확인**이며, 틀려도 우리 쪽에는 아무 신호가 없다.

> 📌 §5 의 "제어 루프의 실제 종착지는 물리 gNB2 의 cell-stop/cell-start 다" 는 2026-09-15 이후
> **절반만 맞다** — 15f 는 gNB2 로, 14_e 는 UPF 로 따로 나간다. §5 의 서술 자체는 15F 수신 경로만
> 다루므로 그 범위 안에서는 여전히 유효하다.

### NCOF 측 정리 (우선순위 순)

1. ~~**14_e 제어 본문의 하드코딩 값 수정**~~ — **완료** (`1335888`, 2026-09-10 11:11 실기동 확인).
   `apply_qos_policy()` 가 `build_15f_cell_power()` 와 같은 인자를 받아 봉투 29곳을 덮어쓴다.
   `Gnb2RLEngine` 은 `generate_notification` 을 상속받으므로 자동 적용.
   > 하드코딩된 `subscriptionId` 는 이것 하나뿐이었다. `core/15f_….json` 에도 같은 고정값이 있지만
   > 그 파일은 `test.py:22` 의 **주석 처리된 줄**에서만 언급되는 죽은 파일이고, 라이브 15f 는
   > 코드로 생성된다. 저장소 전체 전수 조사 결과 다른 하드코딩 지점은 없다.
2. 🔴 **중복 구독 제거 — 이제 최우선. 2026-09-17 오전에 실제로 터졌다.**
   두두원이 10:02:57 / 10:05:01 / 10:20:18 세 번 재기동하며 매번 구독을 재전송해
   상향 **8** / 하위(`external_subscriptions`) **40** / GUI 간선 **72** 로 정확히 4벌이 쌓였다
   (정상값 2 / 10 / 18). §8.1 이 코드로만 예측했던 것이 회선에서 실증된 것이다.
   20:24 "청소 후 재기동"(§8.1)으로 2 / 10 / 18 복구 — **절차는 먹히지만 두두원 재기동을 우리가 통제할 수 없다.**
   원인은 그대로다: `create_subscription`(`subscription_manager.py:79`)이 `:99` 에서
   `str(uuid.uuid4())` 를 조건 없이 발급하고 `:103` 에서 무조건 삽입한다.
   **선결 과제는 "같은 구독" 의 기준 정의**(`consNfInfo.nfId` + `notificationURI` + 이벤트 집합?)이고,
   정하기 전까지는 절차로만 막힌다(§8.1, 남은 결정 사항 1번).
   > §6 표의 `중복 구독 제거가 없다` 행도 심각도를 **중간 → 높음** 으로 올릴 것 — 더 이상 가설이 아니다.
3. **metric 진동 수정** — 한 구독의 두 UPF 스트림 중 최신 하나만 고르는 대신,
   WLAN_PERFORMANCE 스트림을 명시적으로 선택하거나 두 스트림을 합성. (`data_analyzer.py:213-227`)
4. **`data_analyzer.py:184-185` 필터 정교화** — NEF/UPF 경계만 긋고 WLAN/비-WLAN 경계는 안 긋는다.
5. **규격 원본(`ncof_yaml`) 수정 — 아직 한 건도 착수하지 않았다.** §6.3 기준.
   `main` 최신 커밋은 `a4a0d06`(2026-05-26)이고 9/11 이후 커밋이 없다. 작업트리에 미커밋 수정이 몇 개
   있으나 `Mcc`/`Mnc` pattern·description 정리로 **아래 목록과 무관하다.** 착수 순서 권장:
   ① `_PowerEnergyConsumptionInfo.required` 의 `_PowerEnergyConsData` → `_powerEnergyConsData`
      (규격 버그, `TS29591_Nnef_EventExposure_…yaml:890`·`:893` 에 그대로 남아 있음)
   ② `dlPeakThroughPut` → `dlPeakThroughput` (규격이 회선을 따라감)
   ③ 🔴 **우선순위 상승 (2026-09-17)** — `ncof_json/13p_d_….json` 의 `timestamp` → `timeStamp`,
      `cell-001`/`cell-002` → hex 9자리. **두두원이 9/17 에 자기 쪽을 먼저 고쳤으므로 이제 위반은
      우리 샘플뿐이다.** `main` 실측: `:7`·`:133` 이 `timestamp`, `:36`·`:157` 이 `cell-001`,
      `:95`·`:203` 이 `cell-002`. 회선은 `"123456789"` 로 합격인데 참조 샘플이 틀려
      **대조 기준으로 못 쓰는 상태**다
   ④ NEF 샘플 5종의 `notificationMethod` → `notifMethod`
   ⑤ 키 드리프트 11건 — **`intGroupId` 은 값(`GroupId` 패턴)까지 같이** 고칠 것
   ⑥ `qosMonPending`/`inclRatType`: `false` → **필드 생략**
   ⑦ `14_e` `qosPolAssistSets` 의 `appId`/`fDescs` 중 하나 제거 (`oneOf`)
   ⑧ `13p_d`/`2p_` 파일명 정정 (내용이 아니라 이름)
   ⛔ `validityTimes` 위치는 **두두원과 동시 수정** — 단독 이동 금지
6. ~~두두원이 **소수 초 파싱을 고치면** `_DODO1_NO_FRACTIONAL_SECONDS = False`(패치 A)~~
   — **완료 (`ce71818`, 2026-09-17 20:27 실기동 검증).** 단순히 플래그를 뒤집은 게 아니다:
   하나의 플래그가 (a)마이크로초 제거와 (b)`startTime` 60초 백데이트를 **함께** 게이트하고 있어서,
   회수 후 실패했을 때 원인이 소수 초인지 시계 오차인지 가릴 수 없었다. 백데이트를 `if` 밖으로 빼
   **무조건 적용**으로 바꾸고(`subscription_request_builder.py:70` 상수, `:110` 적용),
   플래그는 (a)만 게이트하도록 분리한 뒤 `False` 로 내렸다(`:89` 선언, `:111` 게이트).
   테스트 `tests/test_target_period.py` 신규 4건이 이 분리를 고정한다.
   실측: 나간 `startTime: 2026-09-17T20:26:54.615759+09:00` — 소수 초가 실렸고 백데이트 60초도 살아 있다.
7. ~~두두원이 **`notificationURI` 오타를 고치면** 패치 C 를 비우고 재검증~~ — **완료 (2026-09-10 17:30).**
   패치 C 제거 후 파일이 도입 이전 블롭과 동일함까지 확인. 상세는 §4.
8. **관대 수신 계층 제거 (패치 B) — 두두원 답신 대기.** "연동이 안정화되면" 이 조건이 아니다.
   조건은 두두원의 `-999` + 정수 필드 소수값 **동시 수정**이다 ↓
9. ~~**고아 하위 구독 해소 + 저장 구독 복원 재활성화**~~ — **완료 (2026-09-10, 실기동 검증)** ↓↓

#### 8 의 상세 — 패치 B(관대 수신) 회수 조건 (2026-09-17 실측)

**지금 `NCOF_LENIENT_INGEST` 를 끄면 수신 통지의 70.1%(3,403건 중 2,384건)가 422 로 죽는다.**
원인은 정확히 둘이고, **두두원이 둘을 동시에 고쳐야** 회수할 수 있다.

| # | 원인 | 영향 통지 | 두두원 출처 |
|---|---|---|---|
| ① | `-999` 센티넬 | 2,384건 (영향 통지의 **100%**) | `ncof_flow_targeting.cpp:21-28`(`Json_Stamp_Number_Default()`), `:56-68`(`Replace_Stamp_One()`), `:83-91`, `:100-107` · `ncof_flow_report_common.cpp:345,363,382,908,911,1219` · `ncof_flow_dynamic_report.cpp:289,311` |
| ② | 정수 필드에 소수값 | 1,363건 (40.1%) | 같은 `Replace_Stamp_One()` 계열. 3GPP 표준 필드(`pdb`·`pdbDl`·`maxPdbUl`·`maxPdbDl`·`dl/ul/rtrPacketDelay`)만으로 1,362건 |

> 🔴 **①만 먼저 고쳐지면 상황이 나빠진다.** 지금 `-999` 에 가려져 있던 AF `PERF_DATA` 682건이
> ②의 소수값 위반으로 새로 드러나, 영향 통지가 최대 **2,045건**까지 늘 수 있다.
> 두두원이 "①만 반영했다" 고 알려 오면 **패치 B 를 끄지 마라.** 회신에서도 ②를 먼저 해 달라고 적었다.

**부분 축소(갈래 제거)는 아직 하지 마라 — 지금의 0회는 갈래가 죽은 증거가 아니다.**
9/17 재기동 이후 창(20:28~20:45, 통지 119건)의 원장은 `DROP_SENTINEL` 3,485 · `ROUND_TO_INT` 874 ·
`CEIL_TO_INT` 268 뿐이고 `_candidates()`(`lenient_ingest.py:110-`)의 `string_type` 갈래(`:123`)와
`value_error` 갈래(`:134`)는 **0회**다. 그러나 `captured/lenient_ledger_sample.jsonl`(2026-09-09~10 창)에는
`STRINGIFY_BITRATE_BPS` 12 · `STRINGIFY_PACKETRATE_PPS` 16 · `STRINGIFY_VOLUME_BYTES` 28 —
**같은 갈래가 56회 발동한 기록이 남아 있다.** 0회가 된 것은 두두원이 9/17 에 단위 접미사를 붙이도록
고쳤기 때문이지 갈래가 불필요해졌기 때문이 아니다. 게다가 **8p 주기보고 경로(682건)는 스루풋 8필드가
100% `-999` 라 이번 단위 수정이 닿지 않았고**, 두두원이 `-999` 를 없앨 때 그 경로가 단위 붙은 문자열을
보낼지 맨 숫자를 보낼지는 아직 모른다. §4 의 🔴 경고(`STRINGIFY_BITRATE_BPS` 를 함부로 건드리지 말 것 —
단위 없는 숫자는 `_parse_mbps` 가 Mbps 로 오인해 10⁶배가 된다)가 겨냥한 필드가 바로 그것이다.

> 축소 착수 조건: 두두원이 `-999` 를 제거한 뒤 **8p 경로가 실제로 단위 붙은 문자열을 보내는 것을
> 원장으로 확인한 다음.** 그때는 `_drop_sentinels()`(`:82-`)와 `int_type` 갈래(`:115`)만 남기면
> 계층의 표면적이 절반 이하로 줄고, 최종 제거 시 지울 코드도 그만큼 줄어든다.

최종 제거 절차는 그대로다 — `NCOF_LENIENT_INGEST` 를 끄고, `core/lenient_ingest.py` 와
`main.py` 의 2줄을 삭제한다.

#### 9 의 상세 — 고아 하위 구독 해소 (2026-09-10)

#### 8 의 상세 — 고아 하위 구독 해소 (2026-09-10)

**실기동 검증 완료 (2026-09-10 22:31, MODE=DEVICE, 두두원 실장비).**

| 확인 지점 | 이전 | 이후 |
|---|---|---|
| 하위 구독 ID 획득 | `ID 를 획득하지 못함` 10건, 채택 0건 | `요청 본문의 notifId 를 채택` **10/10** (`notifId 도 없음` 0건, 연결 오류 0건) |
| `external_subscriptions` | 0건 (구독 2건 모두 빈 배열) | **10건** (PCF 구독 4 + RICF 구독 6), 상태 파일에도 저장됨 |
| GUI 간선(`/api/subscriptions/relations`) | 2건 — 상향 `pcf→ncof`, `ricf→ncof` 뿐 | **18건** — `ncof→smf`×4, `ncof→nef`×6, `nef→af`×3, `nef→ricf`×3 이 추가 |
| 제어 루프 | (동일) | 22:32:30 PCF · 22:32:38 RICF 발송, `제어명령 실패` 0건, `_cellPowerState: DEEP_SLEEP` |
| 잘못된 해지 발송 | — | 0건 (새 상태 파일이라 stale 대상이 없음 — 의도대로) |
| **하위 구독 해지 (2차 검증, 22:37)** | 불가능(ID 가 없어 시도조차 못 함) | **DELETE 10/10 → 실장비 HTTP/2 200 OK**, 404·실패 0건 |

채택된 ID 예: `NOTIFICATION_upf_2026-09-10T22:31:26.057728+09:00` (10건 전부 서로 다름).
`13p_d` 422 거절 1건은 §6.1 대로 의도된 것이고, 분석 메트릭이 `0.0`/`150.0` 을 오가는 것은
§5 의 미결 9번(metric 진동)으로 이번 수정 범위가 아니다.

#### 해지 경로 실증 — 가장 중요한 확인 (2026-09-10 22:37)

1차 검증은 새 상태 파일에서 시작했으므로 해지할 대상이 없었다. 그래서 **커밋(`e49c613`) 후
본 체크아웃으로 기동 위치를 옮길 때 살아 있는 상태 파일을 인계해** 복원이 실제 해지를 수행하게 했다.
복원이 stale 10건을 두두원에 DELETE 한 결과:

```
DELETE :55557//subscriptions/NOTIFICATION_upf_2026-09-10T22:31:26.057728+09:00  "HTTP/2 200 OK"
DELETE :55558//subscriptions/NOTIFICATION_af_2026-09-10T22:31:26.057962+09:00   "HTTP/2 200 OK"
DELETE :55556//subscriptions/NOTIFICATION_ricf_2026-09-10T22:31:26.058023+09:00 "HTTP/2 200 OK"
... (10건 전부 200, 404 0건, 실패 0건)
```

**이것이 이 수정의 핵심 주장에 대한 실증이다.**
- 채택한 notifId 가 두두원에서 진짜 해지 핸들로 동작한다 (200 = 매칭 성공. 값이 안 맞으면 404 다).
- `:` 와 `+` 를 **인코딩하지 않은 판단이 옳았다.** `quote()` 를 씌웠다면 두두원이 `%3A` 를 그대로
  잘라 비교해 10건 전부 404 가 됐을 것이다.
- 장비에 구독이 누적되지 않는다 — 낡은 10건이 지워지고 새 10건이 들어가 총 10건을 유지했다.

이후 제어 루프도 재개됐고(PCF·RICF 각 1건, 실패 0건), `external_subscriptions` 는 새 ID 10건으로
갱신돼 상태 파일에도 저장됐다. 현재 NCOF 는 **본 체크아웃**에서 커밋된 코드로 돌고 있다.

> 📌 **기동 위치를 옮길 때의 절차 (알아 둘 것).** `data/ncof_state.json` 은 **cwd 기준 상대 경로**라
> 기동 디렉터리마다 별개 파일이다. 위치를 옮길 때 낡은 상태 파일을 그대로 쓰면 복원이 **장비가 들고
> 있지 않은 ID** 로 해지를 시도하고(404) 그 위에 새 팬아웃을 얹어 구독이 두 배가 된다. 옮기기 전에
> **살아 있는 상태 파일을 인계하라.** 본 체크아웃의 이전 파일은 `data/ncof_state.json.bak-223706`
> 으로 남겨 뒀다.

| 파일 | 변경 |
|---|---|
| `core/subscription_handler.py` | 추출 체인의 `if not external_sub_id:` 안에 **요청 본문 `notif_id` 폴백** 추가. 기존 "ID 를 획득하지 못함" 경고는 유지(비순응 사실을 숨기지 않는다). 빈 문자열은 `None` 으로 정규화 |
| 같은 파일 | stale 해지 루프를 `teardown_stale_external_subscriptions()` 로 분리 — 만료 구독처럼 `start()` 를 부를 수 없는 경우에도 정리할 수 있게 |
| 같은 파일 | `start(stagger_relations=True)` 파라미터 추가. Phase 2 의 GUI 연출 대기를 끌 수 있다 |
| 같은 파일 `_send_external_unsubscription` | 코드 변경 없음 — **percent-encoding 금지**를 근거와 함께 주석으로 고정 |
| `core/subscription_manager.py` | 만료 저장 구독도 `_teardown_saved_external_subscriptions()` 로 **하위 구독을 해지한 뒤** 버린다 |
| 같은 파일 | `_pending_restore` 도입 — 복원 도중의 상태 저장이 **아직 복원하지 않은 항목을 파일에서 지우는** 문제 차단 |
| 같은 파일 | 복원은 `start(stagger_relations=False)` 로 호출 |
| 같은 파일 `shutdown()` | `list(...)` 스냅샷 순회 — 복원 태스크가 삽입 중이면 `RuntimeError: dictionary changed size` 로 종료가 중단돼 httpx 클라이언트가 누수된다 |
| `main.py` | `restore_persisted_subscriptions()` 재활성화 + **백그라운드 태스크로 분리**, 예외 로깅 헬퍼, 종료 시 취소·회수 |

**왜 notifId 폴백이 맞는 해법인가** — 두두원은 요청 본문의 notifId 를 자기 `subscription_id` 로 채택하고
(`ncof_flow_subscription_handlers.cpp:53-54` 등 6곳), DELETE 는 body `subscriptionId`→`notifId`→`id`→
**경로 마지막 세그먼트** 순으로 ID 를 찾아(`ncof_flow_subscription_core.cpp:1147-1183`)
key/subscription_id/notif_id 중 아무것이나 매칭한다(`:1209`). 응답도 200 `{"result":"deleted"}` /
404 `{"error":"subscription not found"}` 로 갈려 **성공 판별이 가능**하다.
mock NF 3종은 성공 경로에서 항상 uuid4 를 헤더에 실으므로 이 폴백은 **그쪽으로는 도달하지 않는다**.

**남은 결정 사항 (사용자 판단 필요)**

1. 🔴 **중복 구독 트리 — 더 이상 가설이 아니다. 2026-09-17 오전에 실제로 터졌다.**
   두두원이 오전에 3회 재기동(10:02:57 / 10:05:01 / 10:20:18)하며 매번 구독을 재전송해
   상향 8건 · 하위(external) 40건 · GUI 간선 72건까지 불어났다 — 평상시 2 / 10 / 18 의 **정확히 4배**다.
   증거는 `data/ncof_state.json.bak-20260917-202439` — 구독 8건이 PCF(ext 4)·RICF(ext 6) 짝 **4벌**로 들어 있다.
   20:24 "청소 후 재기동"(§8.1)으로 2 / 10 / 18 로 복구했다.
   이전 판의 "두두원을 NCOF 와 **같이** 재기동하면" 과 "지금은 절차로 막았다" 는 둘 다 **반쯤 틀렸다** —
   절차는 **우리 쪽 재기동만** 막을 수 있고 **두두원 단독 재기동은 막지 못한다**(§8.1 표의 "두두원 만" 행).
   `create_subscription` 의 중복 제거는 여전히 미구현이고, "같은 구독" 의 기준
   (`consNfInfo.nfId` + `notificationURI` + 이벤트 집합?)을 정하는 것이 선결 과제다.
   **미결 — 우선순위를 올려 위 "NCOF 측 정리" 에서 함께 다룰 것.**
2. **하위 구독 POST 응답이 4~6초로 늘어난다** — 폴백으로 Phase 2 의 연출 대기가 실제로 돌기 시작한다
   (이전에는 ID 가 없어 `successful` 이 비어 루프 자체가 안 돌았다). 복원 경로는 껐지만
   **두두원이 보내는 실구독 응답은 그만큼 느려진다.** 두두원 `http2_client.cpp` 에 타임아웃 설정이
   **0건**(2026-09-17 재확인 — 걸리는 건 `NGHTTP2_SETTINGS_MAX_CONCURRENT_STREAMS` 뿐)이라
   두두원이 끊지는 않지만, 연출 대기를 응답 경로에서 아예 빼려면 별도 결정이 필요하다.
3. ~~**기존 고아는 회수할 수 없다**~~ — **해소 (2026-09-17 20:24 "청소 후 재기동").**
   이 항목이 근거로 들었던 "현재 상태 파일의 구독 2건은 `external_subscriptions: []`" 는
   **2026-09-10 시점의 상태**였고 지금은 아니다. 20:27 기동분 `/api/handlers` 실측:
   살아 있는 핸들러 2건이 external 을 각각 **4건(PCF, `pcf-uuid-001`)·6건(RICF, `ricf-uuid-001`)** 들고 있고
   ID 는 `NOTIFICATION_upf_2026-09-17T20:27:54.616059+09:00` 형식이다
   (같은 내용이 `data/ncof_state.json.bak-204653` 에 남아 있어 미기동 상태에서도 확인된다).
   두두원에 쌓여 있던 고아도 20:24 청소 + 20:27 장비 재기동으로 함께 사라졌다.
4. **복원 창에서의 404** — 기동 직후 미복원 구독에 대한 `DELETE`/`PUT` 이 404 를 받고 그 뒤 되살아난다.
   503 + `Retry-After` 로 바꾸는 건 northbound 의미 변경이라 착수하지 않았다.

**테스트** (`prototype/nncof-server/tests/`)

- `test_subscription_handler.py` +7건 — 폴백 발동/미발동(헤더·본문 ID 우선), 비-2xx·연결 실패에 유령 ID 없음,
  notifId 부재, 해지 URL 의 `:`/`+` 원문 유지(재-`quote()` 방지 가드)
- `test_main_lifespan.py` 신규 3건 — 복원이 기동을 막지 않음, 종료 시 회수 순서, 복원 실패 로깅.
  **변형 검증**: `cancel()` 삭제 / `await` 회수 삭제 / 회수를 `shutdown()` 뒤로 이동 — 3가지 모두 실패한다
- `test_subscription_restore.py` 신규 5건 — 만료 구독의 해지 선행, 재구독 전 stale 해지 순서,
  복원 중 저장이 미복원 항목을 보존, 복원이 연출 대기를 끔. (오늘까지 이 함수는 테스트 0건이었다)

> 전체 스위트의 실패 4건(`test_{individual_,}ncof_event*_api.py`)은 **사전 실패**다 —
> 미수정 본 체크아웃에서도 같은 `NameError` 로 깨진다(생성 스텁이 주석 처리된 `client.request` 뒤에서 `response` 참조).

### 8.1 재기동 조합별 절차 (2026-09-11 코드 검증 → **2026-09-17 실증**)

**중복의 원인은 복원이 아니라 중복 제거의 부재다.** `create_subscription`
(`subscription_manager.py:92-103`)은 `str(uuid.uuid4())` 를 조건 없이 발급하고(`:99`)
`self.subscriptions[subscription_id] = handler` 로 무조건 삽입한다(`:103`) —
`consNfInfo.nfId`·`notificationURI`·`notifCorrId`·`prevSub`·이벤트 집합 어느 것으로도 조회하지 않는다.
`nf_id` 는 GUI 간선(`:94` → `add_relation(from_node=…)`)과 로그 접두(`:96`)에만 쓰인다.
이 코드는 **커밋 `e49c613` 이 건드리지 않았다.**

> 🔴 **2026-09-17 실증 — 이 절의 경고가 그대로 현실이 됐다.** 두두원이 오전에 3회 재기동하며
> (**10:02:57 / 10:05:01 / 10:20:18**, `logs/app.log` 의 `--- [SUBSCRIPTION] --->` 8건으로 확인)
> 매번 구독을 재전송해 NCOF 에 구독 트리가 **4벌** 쌓였다: 상향 **8** / 하위(external) **40**.
> 근거는 `data/ncof_state.json.bak-20260917-202439` — 구독 8건, external 합계 40건(4건짜리 4 + 6건짜리 4)이
> 그대로 들어 있다. GUI 간선은 **72**(= 18×4)로 기록돼 있다(`두두원_검증결과_회신초안.md` 의 회신 기록.
> relation 은 상태 파일에 영속되지 않아 사후 재측정은 불가).
> 20:24 "청소 후 재기동" 으로 **상향 2 / 하위 10 / 간선 18** 로 복구됐다
> (`data/ncof_state.json.bak-204653`: 구독 2건, external 10건).

**무엇이 몇 배가 되는가 — 실측.**

| 지표 | 1벌 | 3벌(10:10대) | 4벌(10:30대) | 청소 후(20:30대) |
|---|---|---|---|---|
| 분석 타이머 (`AI 분석 시작` /분) | 2 | **6** | **8** | 2 |
| 수신 통지 (`[NOTIFICATION]` /분) | 10 | **30** | 10 | 10 |

- **분석 타이머는 벌 수에 정확히 비례한다** — NCOF 내부 낭비가 그대로 4배가 된다.
- ⚠️ **통지 물량도 늘 수 있다.** 10:10–10:18 9분간 **270건 = 30건/분**으로 **3배**였다
  (AF 81 · RICF 81 · UPF 108 — 구성비 3:3:4 는 그대로, 진폭만 3배).
  그런데 10:20:18 재기동 뒤에는 4벌인데도 **10건/분**으로 되돌아왔다(10:30–10:39 100건).
  즉 통지 물량은 NCOF 의 핸들러 수가 아니라 **두두원 쪽에 살아 있는 등록 세트 수**를 따라가고,
  그건 재기동 방식에 달려 있다. **어느 재기동이 이전 등록을 지우고 어느 것이 남기는지는 미해명이다**
  (두두원 로그 부재. 구 인스턴스 동시 구동 가능성도 배제하지 못했다).
  따라서 "중복은 NCOF 내부 문제일 뿐" 이라고 **단정하면 안 된다** — 회선 부하까지 배수로 커진 구간이 실재한다.

| 재기동 | 결과 | 절차 |
|---|---|---|
| **NCOF 만** | ✅ 안전. 복원이 상향 구독을 같은 ID 로 되살리고, 낡은 하위 구독을 DELETE 한 뒤 재구독한다(실측 10/10 200) | 그냥 재기동. 두두원 손대지 말 것 |
| **두두원 만** | 🔴 **9/17 에 실제로 3회 터진 조합.** 재기동 1회마다 상향 +2 / NCOF 기록상 하위 +10 / 간선 +18 이 얹히고 고아 핸들러가 잔존한다. **장비에 그 세트가 실재하는지는 재기동 방식에 따라 다르다** — 9/10 검증에서는 기록 20건에 장비 실재 10건이었으나, 9/17 10:10대에는 최소 3세트가 살아 통지가 3배로 들어왔다. **`e49c613` 이전에도 동일했다** | 아래 "정리 절차" 로 고아 해지, 또는 "청소 후 재기동" |
| **둘 다** | ⚠️ 복원 2건 + 두두원 신규 2건 = 4건. 예전 코드에서는 정상이던 조합이 이제 해롭다 | "청소 후 재기동" 을 쓸 것 |

> ⚠️ **"두두원 만" 은 우리가 막을 수단이 없다.** 9/17 회신에서 재기동 전 사전 공유를 요청해 뒀지만,
> 근본 해소는 NCOF 쪽 중복 제거뿐이다(§8 목록 2번).

**청소 후 재기동** (순서가 절대적이다 — 두두원은 기동 시 1회만 구독을 보내므로 NCOF 가 먼저 떠 있어야 한다).
**2026-09-17 20:24 에 이 절차로 4벌 중복을 실제로 정리했다 — §8.1 의 우려가 실증된 뒤의 복구 실적이다.**

1. NCOF 정지 (pid 로 SIGTERM. `pkill -f`/`pgrep -f` 는 자기 명령줄까지 매칭해 셸이 죽는다 — `hypercor[n]` 처럼 회피 패턴을 쓸 것)
2. 상태 파일 치우기 — **`data/ncof_state.json` 은 cwd 기준 상대 경로**(`persistence_store.py:21-22`)이므로
   **기동 디렉터리의 것**을 치워야 한다. **지우지 말고 `ncof_state.json.bak-<타임스탬프>` 로 옮길 것** —
   9/17 에는 이 백업(`bak-20260917-202439`)이 중복 4벌을 사후 입증한 유일한 근거였다
3. NCOF 기동 후 `:9000` 리스닝 확인
4. 두두원 기동 — 두두원 쪽은 우리가 못 올리므로 담당자에게 요청해야 한다

| 지표 | 청소 전 | 청소 후 |
|---|---|---|
| 상향 구독 | 8 | **2** |
| 하위(external) 구독 | 40 | **10** |
| GUI 간선 | 72 (4벌 환산) | **18** |

> 출처: 상향·하위 수치는 상태 파일 백업 `ncof_state.json.bak-20260917-202439`(20:24:32) 와
> `ncof_state.json.bak-204653`(20:45:05) 을 직접 재계산한 값이다. 간선 18 은 20:27 실기동 관측값으로
> §5 의 정상 기준(586행)과 같다. 상태 파일은 relation 을 저장하지 않으므로 **청소 전 72 는 재검증 불가**,
> 18×4 환산값이다.

> ⚠️ **지금은 기동 디렉터리에 `data/ncof_state.json` 이 없다.** 20:46 에 `ncof_state.json.bak-204653`
> 으로 옮긴 뒤 NCOF 가 내려가 있어(실측: `hypercorn` 프로세스 0건, `:9000` LISTEN 없음,
> `curl :9000` → connection refused) 다시 쓰이지 않았다. **이 상태에서는 위 표의 "NCOF 만 재기동 ✅ 안전"
> 이 성립하지 않는다** — 복원이 읽을 파일이 없어 하위 구독 10건이 장비에 고아로 남는다.
> 다만 **`bak-204653` 이 청소 후 트리(상향 2 / external 10)를 그대로 담고 있으므로**,
> NCOF 만 올릴 생각이면 **먼저 `ncof_state.json.bak-204653` 을 `ncof_state.json` 으로 되돌려라.**
> (구독 PUT 등으로 상태 저장을 새로 유발하는 방식은 장비 실재 10건과 어긋난 트리를 만들 수 있어 쓰지 말 것.)
> 두두원까지 함께 올릴 거라면 위 "청소 후 재기동" 조합을 그대로 쓰면 된다.

**정리 절차 (이미 중복된 상태의 복구).** 고아 상향 구독을 northbound 로 해지하면 깨끗이 정리된다:
`DELETE /subscriptions/{id}` → `delete_subscription`(`subscription_manager.py:128-171`) → `handler.stop()`
→ `external_subscriptions` 순회 해지(장비에 없으면 404 인데 `_send_external_unsubscription` 이 404 를 성공으로
처리한다) → relation 제거 → 상태 저장. **이 경로는 `e49c613` 이후에야 실효가 있다** — 이전에는
`external_subscriptions` 가 항상 비어 DELETE 를 한 건도 보내지 않았다.
어느 것이 고아인지는 `/api/handlers` 로 구분한다 — 생성 시각 필드는 없지만 `external_sub_id` 에
ISO 타임스탬프가 박혀 있어(`NOTIFICATION_upf_2026-09-10T22:37:20…`) **오래된 쪽이 고아**다.

> 📌 **정정.** 이 문서의 이전 판은 중복 시 "팬아웃과 제어 명령 발송이 그대로 2배가 된다" 고 적었다.
> **제어 명령은 2배가 되지 않는다.** `generate_notification()`(`gnb2_rule_engine.py:47-49`)의
> `if new_state == self.last_emitted_state: return None` 게이트가 PCF·RICF 양쪽 제어 본문 생성보다
> **앞**에 있고, `data_analyzer.py:262-263` 이 `None` 이면 즉시 반환한다. 고아 핸들러는 얼어붙은
> 데이터를 계속 분석하므로 판정이 바뀌지 않아 **최대 1회 더 내보낸 뒤 영구히 조용해진다.**
> 실제로 2배가 되는 것은 상향 구독 건수·NCOF 기록상 하위 구독 수·GUI `ANALYZING` 펄스(2→4회/분)다.
> (역설적으로 미결 7번 emit-on-change 결함이 여기서는 완충 장치로 작동한다.)

### 참고 — 기동 시 주의

- ⚠️ **운영 절차가 바뀌었다 (2026-09-10).** `restore_persisted_subscriptions()` 가 **다시 켜졌고
  백그라운드 태스크로 돈다**(`main.py` lifespan). 재기동 조합별 절차는 §8.1 을 볼 것.
  요지: **NCOF 만 재기동하면 된다. 두두원을 함께 올리면 구독 트리가 두 벌이 된다.**
- 복원은 기동을 막지 않는다 — 기동 직후 수십 초 동안은 저장 구독이 아직 안 올라와 있어
  `GET /subscriptions`·GUI 목록이 불완전하게 보이고, 그 창에서 들어온 `DELETE`/`PUT` 은 404 를 받는다.
  (복원이 그 뒤에 해당 구독을 되살리므로 그 창에서의 해지는 신뢰하지 말 것.)
- `NCOF_LENIENT_INGEST=1` 를 빠뜨리면 통지가 전부 422 로 거절되고 루프가 돌지 않는다.
  기동 로그 첫머리의 `[LENIENT] 임시 관대 수신 계층 활성화` 배너로 확인할 것(`lenient_ingest.py:398`).
  **아직 끄면 안 된다** — 두두원 9/17 수정 이후에도 `-999` 센티넬과 정수 필드 소수값이 남아 있어,
  지금 끄면 수신 통지의 **70.1%(2,384/3,403)가 422** 다. 회수 조건은 §8 "다음 할 일" 7번을 볼 것.
- 🆕 **패치 A 는 회수됐다 (2026-09-17, `ce71818`).** `_DODO1_NO_FRACTIONAL_SECONDS` 가 `False` 로
  내려가 NCOF 는 이제 `targetPeriod` 에 **소수 초를 실어 보낸다**(`subscription_request_builder.py:89`).
  두두원이 **9/17 10:02 이전 바이너리로 롤백되면** 구 파서가 소수 초에서 `ret==8` 을 반환해
  `start_epoch` 이 **+9시간 미래**로 잡힌다(원리는 §4 `131cc03`).
  증상은 "통지가 한 건도 안 온다" 가 **아니다** — 구독 응답은 200 이고
  **NEF 계열 4종(`9_`·`10_a`·`11p_b`·`13p_d`)은 그대로 오는데, `targetPeriod` 를 쓰는
  UPF 계열(`8_`·`8p_`·`12_c`·`12p_c`)만 0건**이 된다. 이 조합이 보이면
  `ssh dodo1 stat -c %y ~/SBI/app/sbi_poc_app` 로 빌드 시각이 `2026-09-17 10:02` 이상인지 먼저 보고,
  구 바이너리면 `subscription_request_builder.py:89` 를 `True` 로 되돌린다.
  `startTime` 60초 백데이트(`_DODO1_START_BACKDATE`)는 이 플래그와 **무관하게 항상** 적용되므로
  건드릴 필요가 없다 — 이 분리는 `tests/test_target_period.py` 4건이 지킨다.
- 장기 실행 시 fd 누수로 로그가 폭주하므로 `ulimit -n` 을 올려서 띄우는 편이 안전하다.
  실증이 그대로 남아 있다 — `logs/app.log.2026-09-04` 가 **11.9GB** 다.
- 🆕 **기동 전에 디스크도 본다.** 관대 수신 계층은 **위반 통지마다** 원장 1줄과 `*.raw.json` 덤프
  1개를 남기고(무오류 통지는 아무것도 안 남긴다), **자동 회전이 없다** — `lenient_ingest.py:251` 이
  `ledger.jsonl` 에 append 만 한다. 9/17 **수동** 회전분
  `logs/lenient_ingest/ledger.jsonl.upto-20260917-202439` 가 **487MB**, 덤프가 **78,023개**로
  `logs/lenient_ingest/` 가 총 **940MB** 다. 장기 기동 전에는 한 번 비우거나 옮겨 둘 것.
- 🔴 **`MODE=DEVICE` 실기동은 반드시 본 체크아웃(`/home/labry/git/ncof_generated`)에서 하라.**
  `nrf.py:13-23` 의 `_find_upwards` 가 `__file__` 기준으로 `device_info.json` 을 찾는다.
  **커밋된 `prototype/device_info.json` 은 localhost mock 포트(`:9001`/`:9002`/`:9004`)만 담고 있고**,
  두두원 주소(`10.254.173.46:55555-55558`)는 본 체크아웃의 **미커밋 사본에만** 있다.
  `.claude/worktrees/*` 에서 띄우면 두두원이 아니라 mock 을 때리면서 200 을 정상으로 받는다 — 조용히 틀린다.
---

## 9. 참고 자료

### 이 디렉터리의 문서 (`prototype/docs/dodo1-interop/`)

| 문서 | 상태 |
|---|---|
| `HANDOFF.md` | 이 문서 |
| `두두원_수정요청_메일초안.md` (`62170fc`, `ba8c7d4` 에서 `_nodeAddrs` 문구 정정) | 1차 요청 4건. **발송 완료** — 두두원 9/17 수정분이 그 회신이다 |
| `두두원_검증결과_회신초안.md` (`ba8c7d4`) | 9/17 검증 결과 회신의 내부 초안. 검증 창 `2026-09-17 10:07:06~15:23:01` |
| `두두원_회신_발송본.md` (**미커밋**, 9/17 20:36) | 실제로 나간 회신 본문. 후속 요청 2 · 확인 요청 2 · 협조 요청 1 |

> ⚠️ `두두원_회신_발송본.md` 은 아직 커밋되지 않았다. **다음 커밋에 반드시 포함시킬 것** —
> 이후 왕복의 기준이 되는 문서다.
> `두두원_검증결과_회신초안.md` 와 `ba8c7d4` 커밋 메시지는 관대 계층 조기 반환 위치를
> `lenient_ingest.py:353-356` 으로 적었는데 **오기다. 실제는 `:358-359`** (아래 참조).

### 캡처된 본문 — `captured/`

- `captured/` — 두두원이 실제로 보낸 본문(`8_`, `9_`, `10_a`, `11p_b`, `13p_d`, 구독 `1_`/`1p_`)과
  NCOF 가 보낸 하위 구독 6건(`payload_1..6.json`).
  🔴 **전부 2026-09-09~09-10 스냅샷이다. 두두원 9/17 수정분은 반영돼 있지 않다.**
  특히 `captured/13p_d_….json` 은 **수정 전** 본문이라 현행 회선과 키 이름·구조가 다르다 —
  `_powerEnergyConsInfos`(현행 `_powerEnergyConsumptionInfos`), 소문자 `timestamp`(현행 `timeStamp`),
  `_nodeAddrs` 가 배열(현행 단일 객체). **그대로 회귀 대조에 쓰면 틀린다.** 9/17 이후 원문을 새로 캡처할 것.
  (반면 `8_` 의 스루풋 10필드는 캡처본도 현행도 모두 `"-999"` 라 그 부분은 아직 유효하다.)
- `captured/lenient_ledger_sample.jsonl` — 관대 수신 원장 샘플 12건
- `captured/14_e_control_NCOF_to_PCF_BEFORE_envelope_fix.json` — 2026-09-10 09:39:30 에 PCF 로
  보내 200 을 받은 실제 제어 본문. **수정 전** 상태라 템플릿 고정 `subscriptionId`/시각이 그대로 보인다
- `captured/14_e_control_NCOF_to_PCF_AFTER_envelope_fix.json` — 같은 경로, `1335888` 적용 후
  11:11:42 전송분. 라이브 구독 id·현재 시각·`scenario2` 베이스가 반영돼 있다(회귀 비교용 쌍)
- `captured/15_f_control_NCOF_to_RICF_sent_2026-09-10_pretty.json` — 같은 시각 RICF 로 보내 200 을 받은
  실제 제어 본문(`_cellPowerState: DEEP_SLEEP`, `gNBValue: 000002`)

### 회전된 원장·상태 파일 — 9/17 검증의 근거

| 파일 | 내용 |
|---|---|
| `logs/lenient_ingest/ledger.jsonl.upto-20260917-202439` (487MB) | **2026-09-09 23:49 ~ 09-17 15:23 전체 이력.** 9/17 검증 창(10:07:06~15:23:01)의 근거가 전부 여기 있다 |
| `logs/lenient_ingest/ledger.jsonl` | 9/17 20:24 청소·재기동 이후분만. 20:28:55 부터 119행 |
| `logs/lenient_ingest/*.raw.json` (78,023개) | 관대 계층이 **수리한** 통지의 원문. 파일명 앞쪽이 `HHMMSS_마이크로초` 라 mtime 으로 일자 분리가 된다 |
| `data/ncof_state.json.bak-20260917-202439` | **구독 트리 4벌 중복의 증거** — 상향 구독 8건 / external 합계 40건 |
| `data/ncof_state.json.bak-204653` | 9/17 20:46 정리 직후 — 구독 2건 / external 10건(정상 1벌) |
| `logs/app.log.2026-09-{02,03,04,07,08,09,10,…,16}` | 일자별 회전. **9/4 분은 11.9GB**(fd 누수 폭주) — 열지 말 것 |

> ⚠️ 위 회전 때문에 **474행·536행의 "전체 원장 = `logs/lenient_ingest/ledger.jsonl`" 은 더 이상 맞지 않다.**
> 9/17 20:24 이전 데이터는 전부 `ledger.jsonl.upto-20260917-202439` 에 있다.

> 🔴 **"원장·덤프에 없다 = 안 왔다" 가 아니다.** `core/lenient_ingest.py:358-359` 가
> `report["before_error_count"] == 0` 이면 **조기 반환**하며 원장에도 `raw.json` 에도 아무것도 남기지 않는다.
> 즉 **무오류 통지는 기록되지 않는다.** (`:352-353` 의 JSON 파싱 실패 갈래와 헷갈리지 말 것.)
> 그래서 9/17 에 `13p_d` raw 덤프가 0건이 된 것이 곧 **strict 스키마 전수 통과의 증거**였다.
> 실측 — RICF 덤프 중 `13p_d`(수정 전 키 `_powerEnergyConsInfos` 로 판별) 비율:
>
> | 일자 | RICF 덤프 | 그중 `13p_d` |
> |---|---|---|
> | 9/14 | 4,307 | 1,435 |
> | 9/15 | 4,302 | 1,434 |
> | 9/16 | 2,308 | 770 |
> | 9/17 | 715 | **0** |
>
> 9/17 의 715건은 **전부 10:07 이후**(두두원 10:02 재빌드 뒤)이며 전량 `10_a`(`_rfSignalInfos`)다.
> 판별 키를 현행 이름 `_powerEnergyConsumptionInfos` 로 잡으면 **9/16 도 0 이 나와 거꾸로 읽힌다** —
> 수정 전 본문의 키는 `_powerEnergyConsInfos` 이므로 회귀 검증 시 `_powerEnergyCons` 접두로 잡을 것.

### 규격 원본 저장소 — `/home/labry/git/ncof_yaml` (branch `main`)

| 파일 | 역할 |
|---|---|
| `Nncof_EventsSubscription_PoC_ETRI_DoDo1.yaml` | NCOF 자체 API (구독·통지·제어 14_e/15f) |
| `TS29591_Nnef_EventExposure_PoC_ETRI_DoDo1.yaml` | NEF/AF/RICF. `_RfSignalInfo`, `_PowerEnergyConsumptionInfo` |
| `TS29508_Nsmf_EventExposure_PoC_ETRI_DoDo1.yaml` | SMF. `serviveName`(:391) 이 여기 |
| `TS29564_Nupf_EventExposure_PoC_ETRI_DoDo1.yaml` | UPF `NotificationData`, `skipReportingInstruction` |
| `TS29571_CommonData_PoC_ETRI_DoDo1.yaml` | `NrLocation`, `Ncgi`, `NrCellId`, `BitRate`, `GroupId` 등 공통형 |
| `SupplementaryData_PoC_ETRI_DoDo1.yaml` | `AddrFqdn`, `ReportingInformation`, `PerformanceData`, `DispersionCollection` |
| `ncof_json/` | **참조 샘플 25종** — 감사 결과는 §6.3 |
| `callbacks/`, `simplified/` | 생성물. 규격 버그가 여기까지 전파돼 있으니 같이 고쳐야 함 |

> ⚠️ `.claude/worktrees/*` 안의 샘플은 **옛 스냅샷**이다. 반드시 `main` 을 기준으로 볼 것 —
> `_nodeAddrs` 배열 오해가 정확히 이것 때문에 생겼다.

### NCOF 핵심 파일

| 파일 | 역할 |
|---|---|
| `core/subscription_request_builder.py` | 하위 NF 구독 생성. **패치 A 가 여기 있다** — `_DODO1_START_BACKDATE`(`:70`)는 `:110` 에서 플래그와 **무관하게 무조건** 적용, `_DODO1_NO_FRACTIONAL_SECONDS`(`:89`)는 현재 `False`, 게이트 `if` 는 `:111`. 회수된 건 소수 초 제거뿐이다 |
| `core/subscription_handler.py` | 팬아웃 POST `_send_external_subscription`(`:114-172`), 하위 해지 `_send_external_unsubscription`(`:174-221`, **percent-encoding 금지를 근거와 함께 `:188-194` 주석으로 고정** — §7), 제어 발송 `_notify_subscriber`(`:223-283`), stale 정리 `teardown_stale_external_subscriptions`(`:285-298`), `_httpx_kwargs`(`:34-42`). 총 430행 |
| `core/data_analyzer.py` | 주기 분석. `:184-185` 가 UPF(`NotificationData`)만 통과시킴, `:213-227` 이 "최신 UDUM 하나" 를 골라 metric 진동을 만든다(§5), `:262-263` 은 판정 불변 또는 min-dwell 미충족으로 `generate_notification` 이 `None` 을 낼 때의 조기 반환(`gnb2_rule_engine.py:49`, `:57`), `:316-317` 광범위 except |
| `core/decide_wlan_gnb2_rule.py` | `_parse_mbps`(`:160`), `extract_wlan_dl_mbps`(`:173`), `TH_MBPS=500.0`(`:88`) |
| `core/lenient_ingest.py` | 관대 수신 (임시, **패치 B** — 남은 마지막 임시 패치). `_drop_sentinels`(`:82-97`), `_candidates`(`:110-142`, `int_type` `:115` / `string_type` `:123` / `value_error` `:134`), **무오류 통지 조기 반환**(`:358-359`) |
| `core/subscription_manager.py` | `create_subscription`(`:79-126`) — uuid 발급 `:99`, 무조건 삽입 `:103`. **중복 제거가 없다**(§8.1 의 원인) |
| `core/persistence_store.py` | 상태 파일 경로 결정 `:21-22` — `NCOF_STATE_FILE` 또는 **cwd 기준** `data/ncof_state.json` (§8.1 의 2번 절차가 이것 때문) |
| `core/nrf.py` | `MODE=DEVICE` 시 `device_info.json` 로드 |
| `tests/test_target_period.py` | 패치 A 분리의 회귀 가드 4건 (`ce71818`, 72행). `_build_target_period` 는 여태 테스트가 0건이었다 |

> 📌 **이전 판의 "TEMP URI 치환(`:46-70`) — 패치 C 로 줄번호가 뒤로 밀렸다" 는 삭제했다.**
> 패치 C 는 `2a46b75` 로 제거됐고(경위는 §4), 지금 `subscription_handler.py` 에 `TEMP` 라는
> 문자열은 **0건**이다. `:46-70` 은 현재 `SubscriptionHandler` 클래스 선언·docstring·`__init__`
> 영역이라 가리키는 대상 자체가 없다. 위 줄번호는 현행 파일(430행)에서 다시 뜬 값이다.

### 두두원 핵심 소스

⚠️ **2026-09-15~09-17 에 7개 파일이 바뀌고 9/17 10:02 에 재빌드됐다**(`sbi_poc_app` mtime 실측).
아래 줄번호는 **재빌드 후 기준**으로 전부 다시 연 값이다. 이전 판 번호를 쓰면 엉뚱한 곳을 본다.

| 파일 | 역할 | 9/17 전후 |
|---|---|---|
| `src/ncof_flow_common.cpp:421-518` | 메시지 종류 판별 `Detect_Ncof_Recv_Json_Type`(substring 매칭). 14/15F 분기는 `:425-434`, `serviveName` 3계열 내부 분기는 `:455-485`, `Is_7p_Nsmf_Event_Exposure` 는 `:230-248`. `"serviveName"` 매칭은 `:441`. **이전 판의 `:391-488` 은 낡았다** | 변경 9/15 |
| `src/ncof_flow_subscription_core.cpp:208-265` | ISO8601 파서 `Parse_Iso8601_Time_To_Epoch`. `sscanf(…"%d-%d-%dT%d:%d:%lf%c%d:%d"…)` 가 `:228`, `sec=(int)sec_d` 가 `:234` — **소수 초 버그 해소됨**. 소스 전체에 시각 파서는 이것 하나뿐이고 `expiry`(`:450`)·`monDur`(`:379`,`:403`)·`validityTimes`(`:522`) 가 전부 `Check_Ncof_Time_Window_Text_Valid`(`:277-…`)를 거쳐 여기로 모이므로 **셋 다 같이 풀렸다**. **이전 판의 `:208-259` 는 낡았다** | 변경 9/15 |
| `src/ncof_flow_subscription_core.cpp:101-129` | `Select_2p_Report_File` — `_RF_SIGNAL`+`_POWER_ENERGY_CONSUMPTION` 이 **둘 다** 있으면 `2p_both` 로 통합 템플릿(`:112`)을 고른다. 단독일 때만 `_SIGNAL`(`:118`)/`_POWER`(`:124`) | 변경 9/15 |
| `src/ncof_flow_subscription_core.cpp:910-993` | 주기 송신 스케줄러 `Ncof_Subscription_Report_Thread`(1초 폴링). **이전 판의 `:905-981`(§7 은 `:905-984` 로 적어 서로 어긋나 있었다) 은 둘 다 낡았다** | 변경 9/15 |
| `src/ncof_flow_subscription_core.cpp:1157-1193` | DELETE ID 추출 `Extract_Delete_Subscription_Id` — `subscriptionId`(`:1168`) → `notifId`(`:1174`) → `id`(`:1180`) → 경로 마지막 세그먼트(`:1192` → `Extract_Delete_Subscription_Id_From_Path` `:1122-1147`) 순. 3-way 매칭은 `:1219` | 변경 9/15 |
| `src/ncof_flow_subscription_handlers.cpp:26-155` | kind 3/3p 핸들러 `Handle_Recv_3_Nsmf_Event_Exposure`. `8_`/`8p_` 템플릿 선택은 `:88-120`. **이전 판의 `:26-190` 은 옆 함수(`Handle_Recv_2p_Subscription` `:169-243`)까지 삼키고 있었다** | — (9/1) |
| `src/http2_server.cpp:369-379` | 단일 디스패처 + 200/400 응답 생성 (`:369` Detect, `:370` Handle, `:372`/`:376` 분기). 그 밖은 500 | — (8/5) |
| `src/ncof_flow_control.cpp:178-352` | 14_e(NCOF→PCF) 제어 수신 핸들러 `Handle_Recv_14e_Qos_Policy_Assist`. 최상위 JSON 배열 지원은 `:313-325`. **이전 판의 `:138-267` 은 낡았다** | 변경 9/16 |
| **`src/ncof_flow_control.cpp:332-347`** | **신규 — UE 4개가 다 차야 실장비 UPF 로 바이너리 UDP 발사.** 게이트 `udp_fill_count == QOS_APPLY_UE_COUNT` (`:332`), 발사 `Send_Qos_Apply_To_Upf_Udp(config.upf_ip, config.upf_port, packet)` (`:334`). 미달이면 `QOS UDP not sent`(`:345-346`) 로그만 남고 아무 일도 안 일어난다. **NCOF 에 이 경로 가시성 0** | 신규 9/16 |
| `src/ncof_flow_control.cpp:571-628` | 15F(NCOF→RICF) 셀 전력 제어 수신 핸들러 `Handle_Recv_15f_Cell_Power_Ctrl`. 최상위 JSON 배열 지원은 `:607-619`. **이전 판의 `:487-543` 은 낡았다** | 변경 9/16 |
| **`include/upf_qos_udp.h`, `src/upf_qos_udp.cpp`** | **신규 모듈.** 페이로드는 JSON 이 아니라 구조체 바이너리 — `{double gbr_dl; double mbr_dl; char imsi[16];}`(`QosApplyUdpEntry`) × `QOS_APPLY_UE_COUNT(=4)` 고정 길이. `sendto()` 한 방(`upf_qos_udp.cpp:39`). 대상은 두두원 설정의 `upf_ip`/`upf_port`(`config.cpp:90`, `:94`, `config.h:25-26`) | 신규 9/15 |
| ⚠️ `include/upf_qos_packet.h` | **죽은 헤더 — 헷갈리지 마라.** `UpfQosPacket`(magic/version/kbps) 은 `src/`·`include/` 어디서도 include 되지 않는다. 실제 발사 구조체는 위의 `QosApplyUdpPacket` 이다 | — (6/13) |
| `src/db.cpp:287`, `:336` | 수신 제어를 `gnb_control_recv`/`gnb_control` 에 INSERT (어디서도 SELECT 안 함). **줄번호는 9/17 변경 후에도 그대로** | 변경 9/17 |
| `src/ncof_flow_report_common.cpp:826-833` | 송신 토큰표. 단위 접미사 **해소됨** — `Json_Quote("50000000 bps")`(`:829`) 등. `:826-827` 의 `"0.0 Mbps"`/`"1000.0 Mbps"` 는 원래 정상이었다. 헬퍼 `Json_Bps_To_Mbps_Text` 는 `:1211-1240`. **이전 판(§6)의 `:527-539`/`:524`/`:907-934` 는 전부 낡았다** | 변경 9/17 |
| `src/ncof_flow_report_common.cpp:341-357`, `:359-367`, `:370-386`, `:902-911`, `:1211-1240` | `-999` 주입처 — `Json_Metric_Number_Or_999`(`:345`), `Json_Metric_Text_Or_999`(`:363`), RF 단위값(`:382`), Traffic(`:908`, `:911`), Mbps(`:1219`). **이전 판(§6)의 `:225-247` 은 낡았다** | 변경 9/17 |
| `src/ncof_flow_dynamic_report.cpp:289`, `:311` | `8p` 경로 값 주입 — 스루풋 8필드가 100% `"-999"` 인 출처. 이 경로(682건)는 9/17 단위 접미사 수정과 무관하다 | 변경 9/17 |
| `src/ncof_flow_targeting.cpp:21-29`, `:58-75`, `:85-93`, `:102-110` | `Json_Stamp_Number_Default`/`Replace_Stamp_One`/`Json_Qos_Throughput_Default`/`Json_Available_Bitrate_Value` — `-999` 센티넬과 정수 필드 소수값의 **공통 출처**(패치 B 회수의 1·2순위). §6 표의 `:21-29` 와 일치 | — (9/1) |
| `src/ncof_flow_report_db.cpp` | 보고 데이터 DB 조회 | 변경 9/15 |
| `src/gnb_ssh_control.cpp:109`, `:156`, `:160` | `sshpass` 명령 조립(`:109`) → gNB2 로 `eu.gnbControl.py cell-stop`(`:156`) / `cell-start`(`:160`) SSH 셸아웃 | — (7/29) |
| `src/main.cpp:199`, `:239` | 기동 시 1회 구독 발송 — `1_…from_PCF_to_NCOF`(`:199`, `Send_First_PCF_to_NCOF` `:170-208`), `1p_…from_RICF_to_NCOF`(`:239`, `Send_First_RICF_to_NCOF` `:210-248`). 둘 다 `Send_First_Send()`(`:250-262`)가 호출. **이전 판의 `:258` 은 틀렸다 — 그 줄은 실패 분기의 `{` 다** | — (8/7) |
| `src/main.cpp:277-307` | 네 포트(55555~55558) 모두 같은 `Start_Http2_Server` 로 기동. **이전 판의 `:277-306` 은 마지막 스레드 람다를 한 줄 잘라먹었다** | — (8/7) |
| `templates/send/13p_d_….tmpl:178`, `:224` | `"_powerState": "ACTIVE"` 하드코딩 (에코 아님). **이전 판의 `:149`/`:183` 은 9/17 템플릿 수정으로 밀렸다** | 변경 9/17 |
| `templates/send/13p_d_…_POWER.tmpl`(`_powerState` `:53`, `:100`), `…_SIGNAL.tmpl` | 9/17 신설. **회선 미실증이 아니라 현행 NCOF 로는 구조적으로 도달 불가** — NCOF 가 `_RF_SIGNAL` 과 `_POWER_ENERGY_CONSUMPTION` 을 **한 구독에** 함께 싣기 때문에(`subscription_request_builder.py:210-211`, `:241` `eventsSubs=[…, …]`) `Select_2p_Report_File` 이 항상 `2p_both` 로 가고, 실전송은 통합 `13p_d_…v1.0.tmpl` 1종뿐이다 | 신규 9/17 |

> ⚠️ **같은 줄번호가 본문 다른 절에도 박혀 있다 — 같이 고쳐야 문서가 안 깨진다.**
> §3 `Detect…(:391~:488)`→`(:421~:518)`, `main.cpp:277-306`→`:277-307`, `ncof_flow_common.cpp:411`→`:441`,
> 파서 `:226`→`:228`(+버그 해소) / §5 `.tmpl:149,:183`→`:178,:224`, 15F `:487-543`→`:571-628` /
> §6 토큰표 `:527-539`,`:524`→`:826-833`,`:826`(해소됨), `Json_Bps_To_Mbps_Text :907-934`→`:1211-1240`,
> `Json_Metric_*_Or_999 :225-247`→`:341-357`·`:359-367`, `_powerState (:149,:183)`→`(:178,:224)` /
> §6.2 `:1207`→`:1219` / §6.3 `:496,:641,:696`→`:501,:646,:701` /
> §7 `ncof_flow_control.cpp:247-262`,`:523-538`→`:313-325`(14_e)·`:607-619`(15F),
> `main.cpp:277-306`→`:277-307`, 스케줄러 `:905-984`→`:910-993`,
> `ncof_flow_report_common.cpp:458-461`(uuid 리터럴)→`:740-743`,
> `ncof_flow_subscription_core.cpp:1112-1137`→`:1122-1147` / §8 `:1147-1183`→`:1157-1193`.
