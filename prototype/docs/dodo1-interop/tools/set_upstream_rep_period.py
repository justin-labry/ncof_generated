"""NCOF 가 정지된 상태에서 data/ncof_state.json 의 상향 구독 evtReq.repPeriod 를 바꾼다.

사용: python3 -I set_upstream_rep_period.py <state.json> <new_period> <sub_id> [<sub_id> ...]
- 지정한 상향 구독 ID 만 바꾸고, 다른 필드는 건드리지 않는다.
- persistence_store 와 같은 형식(ensure_ascii=False, indent=2)으로 쓴다. 임시 파일 → rename.
"""

import json
import os
import sys


def main() -> int:
    path, new_period, *sub_ids = sys.argv[1:]
    new_period = int(new_period)
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    subs = state["subscriptions"]
    for sid in sub_ids:
        evt_req = subs[sid]["subscription"]["evtReq"]
        print(f"{sid}: evtReq.repPeriod {evt_req.get('repPeriod')} -> {new_period}")
        evt_req["repPeriod"] = new_period
    tmp = path + ".tmp-edit"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
