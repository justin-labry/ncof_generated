"""SIM_SEED 재현성 테스트 (nsmf impl/simulation.py)

서버를 새로 띄워 같은 구독 시나리오를 다시 돌리면 구독별로 동일한 통지 데이터
시퀀스가 나오는지를, 실제 기동과 같은 조건(새 프로세스)에서 검증한다.

각 실행은 일부러 비결정적으로 흔든다.
  - 구독 생성 순서를 섞는다
  - 주기 대기(asyncio.sleep)에 OS 난수로 지터를 넣어 task 간 인터리빙을 바꾼다
  - 대기마다 전역 random 을 임의 횟수 소비한다(다른 모듈이 전역 random 을 쓰는 상황)
  - PYTHONHASHSEED 를 실행마다 다르게 준다
그래도 구독(템플릿)별 시퀀스가 같아야 한다. 타임스탬프는 비교에서 제외한다.

DL throughput High/Low 토글이 벽시계가 아니라 통지 순번으로 정해지는지도 함께 본다.

직접 실행: SIM_SEED=2026 python tests/test_simulation_reproducible.py <shuffle_seed>
"""

import asyncio
import json
import os
import random
import subprocess
import sys
import types

# (구독 키, upfEvents 개수) — subscriptions_collection_api_impl.py 의 템플릿 선택 규칙
#   5개 → 8_..., 3개 → 8p_..., 그 외 → 12_c_...
SCENARIO = [("upf_8", 5), ("upf_8p", 3), ("upf_12c", 1)]
ROUNDS = 5
REP_PERIOD = 10
# 벽시계 시각 필드(datetime.now) — 재현 대상이 아니므로 비교에서 뺀다.
# alias(camelCase), snake_case 둘 다. 3GPP 확장 필드 alias 는 '_' 로 시작(_startTime).
_TIME_KEYS = {"timeStamp", "startTime", "time_stamp", "start_time"}


def _is_time_key(k: str) -> bool:
    return k.lstrip("_") in _TIME_KEYS


def _strip_times(obj):
    if isinstance(obj, dict):
        return {k: _strip_times(v) for k, v in obj.items() if not _is_time_key(k)}
    if isinstance(obj, list):
        return [_strip_times(v) for v in obj]
    return obj


async def _run_scenario(shuffle_seed: int) -> dict:
    from nsmf.impl import subscriptions_collection_api_impl as impl
    from nsmf.models.nsmf_event_exposure import NsmfEventExposure

    jitter = random.SystemRandom()
    real_sleep = asyncio.sleep

    async def fake_sleep(_seconds):
        for _ in range(jitter.randint(0, 5)):
            random.random()  # 전역 스트림 오염
        await real_sleep(jitter.uniform(0, 0.003))

    impl.asyncio = types.SimpleNamespace(
        sleep=fake_sleep, create_task=asyncio.create_task
    )

    sub_name: dict[str, str] = {}
    results: dict[str, list] = {}
    done = asyncio.Event()

    async def fake_notify(sub_id, _uri, payload):
        name = sub_name.get(sub_id)
        if name is None:
            return
        results[name].append(_strip_times(payload))
        if len(results[name]) >= ROUNDS:
            impl._subscriptions.pop(sub_id, None)
            sub_name.pop(sub_id, None)
            if not sub_name:
                done.set()

    impl.utils.notify = fake_notify

    api = impl.NCOFEventsSubscriptionsCollectionApiImpl()
    order = list(SCENARIO)
    random.Random(shuffle_seed).shuffle(order)
    for name, n_events in order:
        subsc = NsmfEventExposure.from_dict(
            {
                "notifUri": f"http://127.0.0.1/cb/{name}",
                "notifId": f"NOTIFICATION_{name}",
                # 10초 주기 → 6초 토글 기준 Low,Low,Low,High,High (양쪽 분기 모두 탐)
                "repPeriod": REP_PERIOD,
                "eventSubs": [
                    {
                        "event": "UPF_EVENT",
                        "upfEvents": [{"type": "QOS_MONITORING"}] * n_events,
                    }
                ],
            }
        )
        resp = await api.create_individual_subcription(subsc)
        sub_name[resp.headers["Subscription-ID"]] = name
        results[name] = []
        await real_sleep(jitter.uniform(0, 0.003))

    await asyncio.wait_for(done.wait(), timeout=30)
    return results


def _run_in_new_process(shuffle_seed: int, sim_seed: str | None, hash_seed: str):
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    env.pop("SIM_SEED", None)
    if sim_seed is not None:
        env["SIM_SEED"] = sim_seed
    out = subprocess.run(
        [sys.executable, __file__, str(shuffle_seed)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_same_sequence_across_restarts():
    a = _run_in_new_process(shuffle_seed=1, sim_seed="2026", hash_seed="1")
    b = _run_in_new_process(shuffle_seed=2, sim_seed="2026", hash_seed="999")
    assert set(a) == {s[0] for s in SCENARIO}
    for name in a:
        assert len(a[name]) == ROUNDS
        assert a[name] == b[name], f"{name}: 재실행 결과가 다름"


def test_different_seed_gives_different_sequence():
    a = _run_in_new_process(shuffle_seed=1, sim_seed="2026", hash_seed="1")
    b = _run_in_new_process(shuffle_seed=1, sim_seed="7", hash_seed="1")
    assert a != b


def test_unseeded_keeps_old_random_behaviour():
    a = _run_in_new_process(shuffle_seed=1, sim_seed=None, hash_seed="1")
    b = _run_in_new_process(shuffle_seed=1, sim_seed=None, hash_seed="1")
    assert a != b


def test_dl_toggle_follows_tick_not_wall_clock():
    from nsmf.impl.simulation import dl_throughput_high_at

    # 6초 토글, 10초 주기: t=10,20,30,40,50 → Low,Low,Low,High,High
    assert [dl_throughput_high_at(t, 10) for t in range(1, 6)] == [
        False,
        False,
        False,
        True,
        True,
    ]


if __name__ == "__main__":
    import logging

    logging.disable(logging.CRITICAL)
    res = asyncio.run(_run_scenario(int(sys.argv[1]) if len(sys.argv) > 1 else 0))
    print(json.dumps(res, sort_keys=True, ensure_ascii=False))
