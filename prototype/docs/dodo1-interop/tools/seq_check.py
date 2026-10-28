"""NCOF 콘솔 로그(밀리초 시각)에서 제어 묶음마다 순서를 판정한다 — 읽기만 한다.

쓰는 법(실장비 로그는 크므로 끝부분만 넘긴다, ANSI 색 코드는 스크립트가 지운다):
  tail -c 50000000 /home/labry/git/ncof_generated/prototype/nncof-server/logs/console.<새 런>.log \
    | python3 -I seq_check.py            # 전체 묶음
  ... | python3 -I seq_check.py --two    # 2건(ON/OFF 전환) 묶음만

판정
  PASS   : 목표 상태 순서(ACTIVE = RICF→PCF, DEEP_SLEEP = PCF→RICF)대로, 앞 대상의 200(·204 — NCOF 성공 기준)을 받은 뒤
           뒤 대상의 본문을 만들었다. 앞 단계가 「겹친 구독만 실패」(다른 구독이 이미 받음)면 그 줄 뒤에 출발했는지 본다
  STOP   : 앞 대상이 실패(500 · 연결 오류 · 타임아웃)했고 뒤 대상은 이 묶음에서 나가지 않았다(약속대로)
  FAIL   : 순서가 다르거나, 앞 200 전에 뒤 대상이 출발했거나, 앞 실패인데 뒤가 나갔다
  1건    : PCF 만(단계만 바뀜) 또는 RICF 만 — 순서 판정 대상 아님, 응답만 보인다
  동시   : GNB2_CONTROL_SEQUENTIAL=0 (예전 동작) 묶음
"""
import io
import itertools
import re
import sys
from datetime import datetime

ANSI = re.compile(r"\x1b\[[0-9;]*m")
TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})\]")
HEAD = re.compile(r"AI 분석 결과: gNB2 (\S+)(.*?) → 구독 (\d+)건 (순차|동시) 전송 \(([^)]*)\)")
POST = re.compile(r'HTTP Request: POST http://[^/]+:(5555[56])/ "HTTP/2 (\d{3})')
FAIL_CODE = re.compile(r"제어명령 실패")
FAIL_NET = re.compile(r"제어명령 전송 중 오류 발생: (.*)")
STATUS = re.compile(r"status_code: (\d+)")
BUILD = re.compile(r"(RICF|PCF) 제어 데이터:")
SEQ = re.compile(r"순차 제어 (\d+)/(\d+) (\S+) (성공 응답 확인|겹친 구독만 실패|실패)")
PORT_NF = {"55555": "PCF", "55556": "RICF"}
OK = ("200", "204")  # subscription_handler 의 성공 기준과 같다


def ts_of(line):
    m = TS.match(line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(microsecond=int(m.group(2)) * 1000)


def judge(b):
    # 같은 NF 가 이어지면(겹친 상향 구독 — 「구독 2건(…) 겹친」 경고) 한 단계로 본다 — v2 의 NF 단계 묶음과 같다
    names = [k for k, _ in itertools.groupby(x.split(":")[0] for x in b["targets"])]
    if b["mode"] == "동시":
        return "동시"
    if len(names) < 2:
        return "1건(실패 — 다음 판정 틱에 다시)" if b["seqfail"] else "1건"
    expect = ["RICF", "PCF"] if b["state"] == "ACTIVE" else ["PCF", "RICF"]
    if names != expect:
        return f"FAIL(목록 순서 {names}, 기대 {expect})"
    first, second = expect
    first_ok = next((t for t, nf, code in b["resp"] if nf == first and code in OK), None)
    first_bad = next((t for t, nf, code in b["resp"] if nf == first and code not in OK), None) or next(
        (t for t, nf in b["neterr"] if nf == first), None
    )
    second_build = next((t for t, nf in b["build"] if nf == second), None)
    second_sent = any(nf == second for _, nf, _ in b["resp"]) or any(nf == second for _, nf in b["neterr"])
    if first_ok is None and first in b["peerheld"]:
        # 앞 단계는 겹친 구독(고아)만 실패 — 500 이든 연결 오류든 — 이고 다른 구독이 이미 받음. 단계 판정 줄 뒤에 출발했으면 순서 맞음
        first_ok = b["peerheld"][first]
    if first_ok is None:
        if second_build is None and not second_sent:
            return "STOP(앞 실패 → 뒤 안 보냄)" if first_bad or b["seqfail"] else "미완(로그 끝)"
        return "FAIL(앞 200 없이 뒤가 나감)"
    if second_build is None:
        return "미완(뒤 본문 없음)"
    if second_build < first_ok:
        return "FAIL(앞 200 전에 뒤 출발)"
    if b["seqfail"] and not any(nf == second and code in OK for _, nf, code in b["resp"]):
        return "PASS(순서) · 뒤 실패 → 다음 판정 틱에 처음부터"
    return "PASS"


def main():
    only_two = "--two" in sys.argv
    blocks, cur, pending_fail_nf = [], None, None
    # tail -c 는 한글 글자 중간에서 자를 수 있다 — 깨진 바이트는 바꿔 읽는다(첫 줄만 깨진다)
    for raw in io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace"):
        line = ANSI.sub("", raw.rstrip("\n"))
        t = ts_of(line)
        m = HEAD.search(line)
        if m:
            cur = {
                "t": t, "state": m.group(1), "split": m.group(2).strip(" ·"), "n": int(m.group(3)),
                "mode": m.group(4), "targets": [x.strip() for x in m.group(5).split(",")],
                "resp": [], "build": [], "neterr": [], "seqfail": False, "seqlog": [], "peerheld": {},
            }
            blocks.append(cur)
            continue
        if cur is None:
            continue
        if (m := BUILD.search(line)):
            cur["build"].append((t, m.group(1)))
        elif (m := POST.search(line)):
            cur["resp"].append((t, PORT_NF[m.group(1)], m.group(2)))
        elif (m := FAIL_NET.search(line)):
            # 어느 대상인지는 바로 앞 본문(제어 데이터) 줄로 짐작한다
            nf = cur["build"][-1][1] if cur["build"] else "?"
            cur["neterr"].append((t, nf))
        elif (m := SEQ.search(line)):
            cur["seqlog"].append(f"{m.group(1)}/{m.group(2)} {m.group(3)} {m.group(4)}")
            if m.group(4) == "실패":
                cur["seqfail"] = True
            elif m.group(4) == "겹친 구독만 실패":
                cur["peerheld"][m.group(3)] = t
    for b in blocks:
        if only_two and len(b["targets"]) < 2:
            continue
        verdict = judge(b)
        t0 = b["t"]

        def rel(t):
            return f"+{(t - t0).total_seconds() * 1000:.0f}ms" if t and t0 else "?"

        resp = " ".join(f"{nf}{code}@{rel(t)}" for t, nf, code in b["resp"])
        build = " ".join(f"{nf}본문@{rel(t)}" for t, nf in b["build"])
        err = " ".join(f"{nf}오류@{rel(t)}" for t, nf in b["neterr"])
        print(f"{t0} {b['state']:<10} {b['mode']} {b['n']}건 [{', '.join(b['targets'])}] {verdict} | {build} | {resp} {err} | {'; '.join(b['seqlog'])}")


if __name__ == "__main__":
    main()
