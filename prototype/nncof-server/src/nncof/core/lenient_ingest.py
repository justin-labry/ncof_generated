"""임시 관대 수신 계층 — 두두원(DoDoWon) 장비 연동 진단용.

목적
----
두두원 sbi_poc_app 이 보내는 통지는 3GPP 스키마를 여러 군데 위반해서
FastAPI/Pydantic 이 **impl 진입 전에** 422 로 거절한다. 애플리케이션 로그가
한 줄도 남지 않으므로 "무엇이 몇 개 틀렸는지" 를 알 수가 없다.

이 모듈은 `NCOF_LENIENT_INGEST=1` 일 때만 활성화되어

  1. 거절되었을 본문의 위반을 **전부** 기록하고,
  2. 알려진 결함 유형을 수리한 뒤 재검증해 **정상 처리 경로로 흘려보내며**,
  3. 무엇을 어떻게 바꿨는지 원장(ledger)에 남긴다.

원본은 언제나 그대로 보존한다(`logs/lenient_ingest/*.raw.json`).

수리 규칙 (실측된 두두원 결함에 대응)
------------------------------------
* ``-999`` / ``"-999"`` 센티넬 → **필드 삭제**.
  3GPP 는 "값 없음" 을 필드 생략으로 표현한다. -999 는 어떤 필드에도 유효하지 않다.
* throughput 계열이 **맨숫자**로 옴 (예: ``dlAverageThroughput: 150000000``)
  → ``"150000000 bps"`` 문자열로 변환.
  **단위 주의**: 두두원은 bps 정수를 보낸다. NCOF 의
  ``decide_wlan_gnb2_rule._parse_mbps()`` 는 단위 접미사가 없으면 **Mbps 로 간주**하므로,
  맨숫자를 그대로 통과시키면 10^6 배 부풀려져 gNB2 가 영구 ACTIVE 로 고정된다.
  ``bps`` 를 명시적으로 붙이는 것이 이 오차를 막는 유일한 방법이며 무손실이다.
* 정수 필드에 소수 → 반올림(하한 제약이 있으면 올림). 서브밀리초 정보는 소실되므로
  원장에 before/after 를 남긴다.

되돌리기
--------
환경변수를 빼고 재기동하면 끝이다. ``install_lenient_ingest()`` 가 즉시 return 하여
미들웨어가 하나도 붙지 않는다. 두두원이 페이로드를 고치면 이 파일을 삭제하고
main.py 의 두 줄을 지우면 된다.

이 파일은 ``src/nncof/core/`` 에 있으므로 OpenAPI 재생성 대상이 아니다
(``.openapi-generator/FILES`` 에 ``src/nncof/core/`` 항목 0건).
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))

# 두두원이 "값 없음" 을 표현하는 데 쓰는 센티넬. 숫자/문자열 양쪽으로 온다.
_SENTINELS = {-999, "-999", "-999.0"}

# 3GPP TS 29.571 BitRate 형식. 이 정규식을 만족해야 모델 검증을 통과한다.
_BITRATE_UNITS = ("bps", "Kbps", "Mbps", "Gbps", "Tbps")


def is_enabled() -> bool:
    return os.getenv("NCOF_LENIENT_INGEST", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _dump_dir() -> Path:
    d = os.getenv("NCOF_LENIENT_DUMP_DIR") or "logs/lenient_ingest"
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# 수리 (repair)
# ---------------------------------------------------------------------------


def _drop_sentinels(node: Any, path: str, ledger: list[dict]) -> Any:
    """``-999`` 센티넬 필드를 통째로 제거한다(3GPP 는 '값 없음'을 생략으로 표현)."""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for k, v in node.items():
            child = f"{path}.{k}" if path else k
            if isinstance(v, (int, float, str)) and not isinstance(v, bool) and v in _SENTINELS:
                ledger.append(
                    {"path": child, "action": "DROP_SENTINEL", "before": v, "after": None}
                )
                continue
            out[k] = _drop_sentinels(v, child, ledger)
        return out
    if isinstance(node, list):
        return [_drop_sentinels(v, f"{path}[{i}]", ledger) for i, v in enumerate(node)]
    return node


def _get_parent(body: Any, loc: list) -> tuple[Any, Any] | None:
    cur = body
    try:
        for p in loc[:-1]:
            cur = cur[p]
        return cur, loc[-1]
    except (KeyError, IndexError, TypeError):
        return None


def _candidates(err_type: str, val: Any) -> list[tuple[Any, str, str]]:
    """(대체값, 액션명, 비고) 후보를 우선순위 순으로 만든다."""
    out: list[tuple[Any, str, str]] = []
    numeric = isinstance(val, (int, float)) and not isinstance(val, bool)

    if err_type == "int_type" and isinstance(val, float):
        r = int(round(val))
        out.append((r, "ROUND_TO_INT", "서브밀리초 정밀도 소실"))
        c = int(math.ceil(val))
        if c != r:
            out.append((c, "CEIL_TO_INT", "하한 제약 때문에 올림"))
        return out

    if err_type == "string_type" and numeric:
        iv = int(val) if float(val).is_integer() else val
        # 스키마가 요구하는 단위는 필드마다 다르다(BitRate/PacketRate/Volume).
        # 후보를 차례로 넣어보고 오류가 사라지는 것을 채택하므로 이름 추측이 필요 없다.
        out.append((str(iv), "STRINGIFY_PLAIN", "숫자를 문자열로"))
        out.append((f"{iv} bps", "STRINGIFY_BITRATE_BPS",
                    "두두원은 bps 정수를 보낸다. 단위를 명시하지 않으면 _parse_mbps 가 Mbps 로 오인해 10^6 배 오차가 난다."))
        out.append((f"{iv} pps", "STRINGIFY_PACKETRATE_PPS", "패킷레이트 필드"))
        out.append((f"{iv} B", "STRINGIFY_VOLUME_BYTES", "트래픽 볼륨(바이트) 필드"))
        return out

    if err_type == "value_error" and isinstance(val, str):
        # 이전 라운드의 잘못된 단위 추정을 교정한다.
        head = val.split(" ")[0]
        if head.replace(".", "", 1).isdigit():
            for unit, act in (("pps", "RETRY_PACKETRATE_PPS"), ("bps", "RETRY_BITRATE_BPS")):
                if not val.endswith(unit):
                    out.append((f"{head} {unit}", act, "단위 재시도"))
            out.append((head, "STRIP_UNIT", "단위 제거 재시도"))
    return out


def _repair_by_errors(model_cls, body: dict, ledger: list[dict], max_rounds: int = 6) -> dict:
    """검증 오류가 가리키는 지점만 후보 대체값으로 고쳐 나간다.

    필드명 추측 대신 **모델이 실제로 낸 오류**를 근거로 삼으므로,
    ``dlAverageThroughput``(bps) 와 ``dlAveragePacketThroughput``(pps),
    ``dlVolume``(순수 숫자 문자열) 처럼 규칙이 다른 필드를 자동으로 구분한다.
    """
    for _ in range(max_rounds):
        errors = _errors_of(model_cls, body)
        if not errors:
            break
        progressed = False
        for err in errors:
            loc = [p for p in err["loc"] if p != "body"]
            got = _get_parent(body, loc)
            if got is None:
                continue
            parent, key = got
            try:
                val = parent[key]
            except (KeyError, IndexError, TypeError):
                continue
            spath = ".".join(str(p) for p in loc)
            for new, action, note in _candidates(err["type"], val):
                parent[key] = new
                still = any(
                    [p for p in e["loc"] if p != "body"] == loc
                    for e in _errors_of(model_cls, body)
                )
                if not still:
                    ledger.append(
                        {"path": spath, "action": action, "before": val,
                         "after": new, "note": note}
                    )
                    progressed = True
                    break
                parent[key] = val
        if not progressed:
            break
    return body


# ---------------------------------------------------------------------------
# 검증 + 기록
# ---------------------------------------------------------------------------


def _errors_of(model_cls, body: dict) -> list[dict]:
    from pydantic import ValidationError

    try:
        model_cls.model_validate(body)
        return []
    except ValidationError as e:
        return e.errors()


def _summarize(errors: list[dict]) -> list[str]:
    from collections import Counter

    c: Counter = Counter()
    for err in errors:
        c[(err["type"], err["msg"][:60])] += 1
    return [f"[{n}회] {t}: {m}" for (t, m), n in c.most_common()]


def repair_and_report(model_cls, raw_body: dict) -> tuple[dict | None, dict]:
    """원본을 수리해 검증 통과본과 리포트를 돌려준다.

    반환값 ``(repaired_or_None, report)``. 수리 후에도 검증에 실패하면 첫 원소는 None.
    """
    before_errors = _errors_of(model_cls, raw_body)
    ledger: list[dict] = []

    repaired = _drop_sentinels(raw_body, "", ledger)
    repaired = _repair_by_errors(model_cls, repaired, ledger)
    after_errors = _errors_of(model_cls, repaired)

    report = {
        "model": model_cls.__name__,
        "before_error_count": len(before_errors),
        "before_summary": _summarize(before_errors),
        "repairs": ledger,
        "after_error_count": len(after_errors),
        "after_summary": _summarize(after_errors),
        "unrepaired": [
            {
                "path": ".".join(str(p) for p in err["loc"] if p != "body"),
                "type": err["type"],
                "msg": err["msg"],
                "input": err.get("input"),
            }
            for err in after_errors[:40]
        ],
    }
    return (repaired if not after_errors else None), report


def _persist(tag: str, raw_body: Any, report: dict) -> None:
    """원본과 리포트를 디스크에 남긴다. 실패해도 수신 경로를 막지 않는다."""
    try:
        stamp = datetime.now(_KST).strftime("%H%M%S_%f")
        d = _dump_dir()
        (d / f"{stamp}_{tag}.raw.json").write_text(
            json.dumps(raw_body, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with (d / "ledger.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps({"ts": datetime.now(_KST).isoformat(), "tag": tag, **report},
                           ensure_ascii=False)
                + "\n"
            )
    except Exception as e:  # noqa: BLE001 — 진단 계층이 본류를 막으면 안 된다
        logger.warning(f"[LENIENT] 덤프 실패(무시): {e}")


def _log_report(tag: str, report: dict) -> None:
    logger.warning(
        "[LENIENT] %s — 위반 %d건 → 수리 %d건 → 잔여 %d건",
        tag,
        report["before_error_count"],
        len(report["repairs"]),
        report["after_error_count"],
    )
    for line in report["before_summary"]:
        logger.warning("[LENIENT]   위반: %s", line)
    for line in report["after_summary"]:
        logger.warning("[LENIENT]   잔여: %s", line)
    for r in report["repairs"][:20]:
        logger.info(
            "[LENIENT]   수리 %s %s: %r → %r", r["action"], r["path"], r["before"], r["after"]
        )
    if len(report["repairs"]) > 20:
        logger.info("[LENIENT]   … 수리 %d건 더 (ledger.jsonl 참조)", len(report["repairs"]) - 20)


# ---------------------------------------------------------------------------
# 설치
# ---------------------------------------------------------------------------


def install_lenient_ingest(app) -> None:
    """`NCOF_LENIENT_INGEST=1` 일 때만 관대 수신 미들웨어를 설치한다."""
    if not is_enabled():
        return

    from starlette.responses import Response

    from nnef.models.nef_event_exposure_notif import NefEventExposureNotif
    from nupf.models.notification_data import NotificationData

    def _model_for(path: str):
        # /notifications/upf/{sub_id} → UPF 스키마, 그 외 /notifications/{nf_type}/{sub_id} → NEF 스키마
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "notifications":
            return NotificationData if parts[1].lower() == "upf" else NefEventExposureNotif
        return None

    class LenientIngestMiddleware:
        """순수 ASGI 미들웨어.

        ``BaseHTTPMiddleware`` 로는 안 된다 — 그 구현의 ``call_next`` 는 미들웨어가
        새로 만든 Request 의 receive 를 쓰지 않고 원본 스트림을 그대로 하위로 넘기기
        때문에, 수리본으로 본문을 갈아끼워도 라우트는 원본을 다시 읽어 422 를 낸다.
        """

        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if (
                scope.get("type") != "http"
                or scope.get("method") != "POST"
                or not scope.get("path", "").startswith("/notifications/")
            ):
                return await self.app(scope, receive, send)

            path = scope["path"]
            model_cls = _model_for(path)
            if model_cls is None:
                return await self.app(scope, receive, send)

            # 본문을 끝까지 읽는다.
            body = b""
            more = True
            while more:
                msg = await receive()
                if msg["type"] == "http.disconnect":
                    return
                body += msg.get("body", b"")
                more = msg.get("more_body", False)

            replay_done = False

            async def replay():
                nonlocal replay_done
                if replay_done:
                    return {"type": "http.disconnect"}
                replay_done = True
                return {"type": "http.request", "body": body, "more_body": False}

            if not body:
                return await self.app(scope, replay, send)

            try:
                raw = json.loads(body)
            except json.JSONDecodeError as e:
                logger.warning("[LENIENT] %s — JSON 파싱 실패: %s", path, e)
                return await self.app(scope, replay, send)

            tag = "_".join(p for p in path.split("/") if p)[:80]
            repaired, report = repair_and_report(model_cls, raw)

            if report["before_error_count"] == 0:
                return await self.app(scope, replay, send)  # 원본이 이미 정상

            _log_report(tag, report)
            _persist(tag, raw, report)

            if repaired is None:
                logger.error(
                    "[LENIENT] %s — 수리 실패, 422 로 거절함. 두두원 수정 필요: %s",
                    tag,
                    report["after_summary"],
                )
                resp = Response(
                    content=json.dumps(
                        {"title": "lenient ingest failed", "detail": report["unrepaired"]},
                        ensure_ascii=False,
                    ),
                    status_code=422,
                    media_type="application/problem+json",
                )
                return await resp(scope, replay, send)

            new_body = json.dumps(repaired).encode("utf-8")
            new_done = False

            async def new_receive():
                nonlocal new_done
                if new_done:
                    return {"type": "http.disconnect"}
                new_done = True
                return {"type": "http.request", "body": new_body, "more_body": False}

            new_scope = dict(scope)
            new_scope["headers"] = [
                (k, v) for (k, v) in scope["headers"] if k.lower() != b"content-length"
            ] + [(b"content-length", str(len(new_body)).encode())]
            return await self.app(new_scope, new_receive, send)

    app.add_middleware(LenientIngestMiddleware)
    logger.warning(
        "[LENIENT] 임시 관대 수신 계층 활성화 (NCOF_LENIENT_INGEST). "
        "두두원 페이로드를 수리해 통과시키며 원장을 %s 에 남깁니다. "
        "연동이 정상화되면 환경변수를 빼고 재기동하십시오.",
        _dump_dir(),
    )
