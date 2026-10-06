"""SIM_SEED 재현성 테스트 (nnef impl/simulation.py)

서버를 새로 띄워 같은 구독 시나리오를 다시 돌리면 구독별로 동일한 통지 데이터
시퀀스가 나오는지를, 실제 기동과 같은 조건(새 프로세스)에서 검증한다.

각 실행은 일부러 비결정적으로 흔든다.
  - 구독 생성 순서를 섞는다
  - 주기 대기(asyncio.sleep)에 OS 난수로 지터를 넣어 task 간 인터리빙을 바꾼다
  - 대기마다 전역 random 을 임의 횟수 소비한다(다른 모듈이 전역 random 을 쓰는 상황)
  - PYTHONHASHSEED 를 실행마다 다르게 준다
그래도 구독(템플릿)별 시퀀스가 같아야 한다. 타임스탬프는 비교에서 제외한다.

직접 실행: SIM_SEED=2026 python tests/test_simulation_reproducible.py <shuffle_seed>
"""

import asyncio
import json
import os
import random
import subprocess
import sys
import types

# (구독 키, 템플릿 파일, 이벤트) — ricf/af_subscriptions_impl.py 의 매핑과 동일
SCENARIO = [
    (
        "ricf_power",
        "13p_d_NncofEventsSubscriptionNotification_from RICF_to_NCOF_v1.0.json",
        "_POWER_ENERGY_CONSUMPTION",
    ),
    (
        "ricf_rf",
        "13p_d_NncofEventsSubscriptionNotification_from RICF_to_NCOF_v1.0.json",
        "_RF_SIGNAL",
    ),
    ("ricf_perf", "10p_a_NefEventExposureNotif_from_RICF_to_NCOF_v1.0.json", "PERF_DATA"),
    ("af_perf_2", "9p_NefEventExposureNotif_from_AF_to_NCOF_v1.0.json", "PERF_DATA"),
    ("af_perf_4", "9_NefEventExposureNotif_from_AF_to_NCOF_v1.0.json", "PERF_DATA"),
    ("af_disp", "11p_b_NefEventExposureNotif_from_AF_to_NCOF_v1.0.json", "DISPERSION"),
]
ROUNDS = 5
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
    from nnef.impl import simulation
    from nnef.models.nef_event_exposure_subsc import NefEventExposureSubsc

    jitter = random.SystemRandom()
    real_sleep = asyncio.sleep

    async def fake_sleep(_seconds):
        for _ in range(jitter.randint(0, 5)):
            random.random()  # 전역 스트림 오염
        await real_sleep(jitter.uniform(0, 0.003))

    simulation.asyncio = types.SimpleNamespace(
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
            simulation.subscriptions.pop(sub_id, None)
            sub_name.pop(sub_id, None)
            if not sub_name:
                done.set()

    simulation.utils.notify = fake_notify

    order = list(SCENARIO)
    random.Random(shuffle_seed).shuffle(order)
    for name, template, event in order:
        subsc = NefEventExposureSubsc.from_dict(
            {
                "notifUri": f"http://127.0.0.1/cb/{name}",
                "notifId": f"NOTIFICATION_{name}",
                "eventsSubs": [{"event": event}],
                "eventsRepInfo": {"repPeriod": 1},
            }
        )
        resp = await simulation.handle_subcription_request(template, subsc)
        sub_id = resp.headers["Subscription-ID"]
        sub_name[sub_id] = name
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
    assert a["ricf_perf"] != b["ricf_perf"]


def test_unseeded_keeps_old_random_behaviour():
    a = _run_in_new_process(shuffle_seed=1, sim_seed=None, hash_seed="1")
    b = _run_in_new_process(shuffle_seed=1, sim_seed=None, hash_seed="1")
    assert a["ricf_perf"] != b["ricf_perf"]


if __name__ == "__main__":
    import logging

    logging.disable(logging.CRITICAL)
    res = asyncio.run(_run_scenario(int(sys.argv[1]) if len(sys.argv) > 1 else 0))
    print(json.dumps(res, sort_keys=True, ensure_ascii=False))
