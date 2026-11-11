# 본문 검증 거절(422) 기록 처리기 테스트
#
# 관대 수신 계층을 끄면 두두원 통지가 422 로 거절돼도 NCOF 로그에는 아무것도 남지
# 않았다(FastAPI 기본 처리기). 거절이 로그·원장에 남고, 상대가 받는 응답은 기본
# 처리기와 같으며, 같은 결함이 반복돼도 원본 덤프는 한 번만 남는지 고정한다.

import json
import logging

import pytest

from nncof.core import validation_reject_log as vrl


@pytest.fixture
def dump_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("NCOF_REJECT_DUMP_DIR", str(tmp_path))
    monkeypatch.setattr(vrl, "reject_counts", vrl.Counter())
    monkeypatch.setattr(vrl, "_dumped_signatures", set())
    return tmp_path


# notificationItems 는 min_length=1, achievedSampRatio 는 1~100 정수
_BAD_UPF = {"notificationItems": [], "achievedSampRatio": 0.5}


def test_rejection_is_logged_and_response_unchanged(client, dump_dir, caplog):
    with caplog.at_level(logging.WARNING, logger=vrl.__name__):
        resp = client.post("/notifications/upf/sub-1", json=_BAD_UPF)

    assert resp.status_code == 422
    # FastAPI 기본 처리기와 같은 모양 — 두두원이 받는 응답은 바뀌지 않는다
    detail = resp.json()["detail"]
    assert {tuple(e["loc"]) for e in detail} >= {("body", "notificationItems")}

    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[422]")]
    assert len(lines) == 1
    assert "/notifications/upf/sub-1" in lines[0]
    assert "누적 notifications/upf 1건" in lines[0]

    ledger = [json.loads(x) for x in (dump_dir / "ledger.jsonl").read_text().splitlines()]
    assert len(ledger) == 1
    assert ledger[0]["path"] == "/notifications/upf/sub-1"
    assert ledger[0]["error_count"] == len(detail)
    raw = dump_dir / ledger[0]["raw_file"]
    assert json.loads(raw.read_text()) == _BAD_UPF


def test_same_defect_dumps_raw_once_but_ledgers_every_time(client, dump_dir):
    for sub_id in ("a", "b", "c"):
        assert client.post(f"/notifications/upf/{sub_id}", json=_BAD_UPF).status_code == 422

    ledger = [json.loads(x) for x in (dump_dir / "ledger.jsonl").read_text().splitlines()]
    assert len(ledger) == 3
    assert [e["raw_file"] is not None for e in ledger] == [True, False, False]
    assert len(list(dump_dir.glob("*.raw.json"))) == 1
    assert vrl.reject_counts["notifications/upf"] == 3


def test_nef_path_counted_separately(client, dump_dir):
    assert client.post("/notifications/af/x", json={"notifId": 1}).status_code == 422
    assert client.post("/notifications/upf/x", json=_BAD_UPF).status_code == 422
    assert vrl.reject_counts["notifications/af"] == 1
    assert vrl.reject_counts["notifications/upf"] == 1
    # 경로 종류가 다르면 원본도 따로 남는다
    assert len(list(dump_dir.glob("*.raw.json"))) == 2


def test_dump_failure_does_not_change_response(client, monkeypatch, tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    monkeypatch.setenv("NCOF_REJECT_DUMP_DIR", str(blocker / "sub"))
    monkeypatch.setattr(vrl, "_dumped_signatures", set())
    assert client.post("/notifications/upf/x", json=_BAD_UPF).status_code == 422
