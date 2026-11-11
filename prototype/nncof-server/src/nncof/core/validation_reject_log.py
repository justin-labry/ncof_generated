"""요청 검증 거절(422) 기록 — 상시 활성.

FastAPI 는 본문이 모델 검증에 실패하면 impl 진입 전에 422 를 돌려준다. 기본 처리기는
아무 로그도 남기지 않고 hypercorn 접근 로그도 꺼져 있어, 두두원 통지가 거절되면
"거절됨" 과 "안 옴" 을 NCOF 쪽에서 구별할 수 없다. 관대 수신 계층(lenient_ingest)을
걷어 내면 그 공백이 그대로 드러나므로, 환경변수와 무관하게 거절을 남긴다.

* 거절마다 WARNING 1줄(경로·위반 요약·누적 건수)
* 거절마다 원장 1줄 ``logs/rejected_422/ledger.jsonl``
* 원본 본문은 (경로 종류, 위반 유형) 조합마다 처음 한 번만 ``*.raw.json`` 으로 —
  같은 결함이 매분 반복돼도 디스크가 불어나지 않게 한다

응답은 FastAPI 기본 처리기에 그대로 넘기므로 상대가 받는 422 본문은 바뀌지 않는다.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))

# 경로별 누적 거절 건수(프로세스 수명 동안)
reject_counts: Counter = Counter()
# 원본을 이미 남긴 (경로 종류, 위반 유형 집합) 조합
_dumped_signatures: set[tuple[str, tuple[str, ...]]] = set()


def _dump_dir() -> Path:
    p = Path(os.getenv("NCOF_REJECT_DUMP_DIR") or "logs/rejected_422")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _path_kind(path: str) -> str:
    """구독 ID 를 뺀 경로 종류. /notifications/upf/<id> → notifications/upf"""
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "notifications":
        return "/".join(parts[:2])
    return "/".join(parts[:2]) or "/"


def _summarize(errors: list[dict]) -> list[str]:
    c: Counter = Counter()
    for err in errors:
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        c[(err.get("type", "?"), loc)] += 1
    return [f"{t} @ {loc}" + (f" ×{n}" if n > 1 else "") for (t, loc), n in c.most_common()]


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


def record_rejection(method: str, path: str, errors: list[dict], body: Any) -> None:
    """거절 1건을 로그·원장·(새 유형이면) 원본 덤프로 남긴다. 실패해도 응답을 막지 않는다."""
    kind = _path_kind(path)
    reject_counts[kind] += 1
    summary = _summarize(errors)
    logger.warning(
        "[422] %s %s — 검증 위반 %d건 (누적 %s %d건): %s",
        method,
        path,
        len(errors),
        kind,
        reject_counts[kind],
        "; ".join(summary[:8]) + (f" … 외 {len(summary) - 8}종" if len(summary) > 8 else ""),
    )
    try:
        d = _dump_dir()
        now = datetime.now(_KST)
        signature = (kind, tuple(sorted({e.get("type", "?") for e in errors})))
        raw_file = None
        if signature not in _dumped_signatures:
            _dumped_signatures.add(signature)
            raw_file = f"{now.strftime('%Y%m%d_%H%M%S_%f')}_{kind.replace('/', '_')}.raw.json"
            (d / raw_file).write_text(
                json.dumps(_jsonable(body), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        with (d / "ledger.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "ts": now.isoformat(),
                        "method": method,
                        "path": path,
                        "error_count": len(errors),
                        "summary": summary,
                        "errors": [
                            {
                                "loc": [str(p) for p in e.get("loc", ())],
                                "type": e.get("type"),
                                "msg": e.get("msg"),
                                "input": _jsonable(e.get("input")),
                            }
                            for e in errors[:40]
                        ],
                        "raw_file": raw_file,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception as e:  # noqa: BLE001 — 기록 실패가 응답을 바꾸면 안 된다
        logger.warning("[422] 거절 기록 실패(무시): %s", e)


def install_validation_reject_log(app) -> None:
    """RequestValidationError 처리기를 등록한다 — 기록 후 FastAPI 기본 응답 그대로."""
    from fastapi.exception_handlers import request_validation_exception_handler
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def _log_and_reject(request, exc: RequestValidationError):
        record_rejection(request.method, request.url.path, exc.errors(), exc.body)
        return await request_validation_exception_handler(request, exc)
