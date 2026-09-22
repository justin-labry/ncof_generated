"""두두원 `Validate_Nsmf_Traffic_Filter_Ips()` 계약을 고정하는 회귀 시험.

2026-09-22 두두원 빌드가 `3_`(Nsmf Event Exposure) 구독의 trafficFilter 를 검증하기
시작하면서 우리 구독이 400 으로 거절됐다. 원인은 둘이었다:

  1. packFiltId 가 permit 규칙의 crc32(예: "3902242897") 라 두두원
     `traffic_filter_setting` 테이블에 존재하지 않았다.
  2. flowDescription 이 "permit in ip from any to any" 라 IP 가 없어
     두두원 정규식이 매치에 실패했다.

아래 시험은 두두원 C++ 쪽 정규식과 비교 로직을 **그대로 복제**해서, 우리가 만드는
필터가 실제로 통과하는지를 확인한다. 두두원 소스가 바뀌면 여기도 같이 고쳐야 한다.
근거: dodo1:/home/dodo1/SBI/app/src/ncof_flow_subscription_handlers.cpp
      (Parse_Traffic_Filter_Flow_Ip_Local / Validate_Nsmf_Traffic_Filter_Ips)
"""

import re

import pytest

from nncof.core.subscription_request_builder import _build_traffic_filter


# dodo1 Parse_Traffic_Filter_Flow_Ip_Local() 의 정규식을 그대로 옮긴 것
DODO1_FLOW_RX = re.compile(
    r"from\s+([0-9]{1,3}(?:\.[0-9]{1,3}){3})(?:/[0-9]+)?(?:\s+[0-9]+)?"
    r"\s+to\s+([0-9]{1,3}(?:\.[0-9]{1,3}){3})",
    re.IGNORECASE,
)

# dodo1 poc_test.traffic_filter_setting 라이브 SELECT (2026-09-22).
# ⚠️ ~/SBI/app/poc_test.sql 의 seed(192.168.105.x / 205.x)는 낡았다.
DODO1_TRAFFIC_FILTER_SETTING = {
    "filter-001-ul": "192.168.101.10",
    "filter-001-dl": "192.168.101.10",
    "filter-002-ul": "192.168.102.10",
    "filter-002-dl": "192.168.102.10",
    "filter-003-ul": "192.168.103.10",
    "filter-003-dl": "192.168.103.10",
    "filter-004-ul": "192.168.104.10",
    "filter-004-dl": "192.168.104.10",
}

DEVICE_SUPIS = [
    "imsi-001010070000101",
    "imsi-001010070000102",
    "imsi-001010070000103",
    "imsi-001010070000104",
]


def dodo1_validate(traffic_filters):
    """두두원 Validate_Nsmf_Traffic_Filter_Ips() 재현. 통과하면 검사 건수를 돌려준다."""
    checked = 0
    for tf in traffic_filters:
        pack_filt_id = tf.pack_filt_id
        flow_description = tf.flow_description
        flow_direction = tf.flow_direction

        # 필수값 공백 검사
        assert pack_filt_id, "packFiltId 가 비었다 → 두두원이 400"
        assert flow_description, "flowDescription 이 비었다 → 두두원이 400"
        assert flow_direction, "flowDirection 이 비었다 → 두두원이 400"

        # 1) DB 조회
        expected_ip = DODO1_TRAFFIC_FILTER_SETTING.get(pack_filt_id)
        assert expected_ip is not None, (
            f"packFiltId={pack_filt_id} 가 두두원 traffic_filter_setting 에 없다 → 400"
        )

        # 2) flowDescription 에서 IP 추출
        m = DODO1_FLOW_RX.search(flow_description)
        assert m is not None, (
            f"flowDescription 정규식 매치 실패 → 400: {flow_description!r}"
        )
        from_ip, to_ip = m.group(1), m.group(2)

        # 3) 방향별 비교
        if flow_direction == "UPLINK":
            recv_ip = from_ip
        elif flow_direction == "DOWNLINK":
            recv_ip = to_ip
        else:
            pytest.fail(f"invalid flowDirection={flow_direction}")

        assert recv_ip == expected_ip, (
            f"IP 불일치 packFiltId={pack_filt_id} direction={flow_direction} "
            f"recvIp={recv_ip} expectedIp={expected_ip} → 400"
        )
        checked += 1

    assert checked > 0, "checked_count <= 0 → 두두원이 400"
    return checked


@pytest.mark.parametrize("supi", DEVICE_SUPIS)
def test_device_supi_passes_dodo1_validation(supi):
    """실장비 SUPI 4종이 두두원 검증을 통과해야 한다."""
    filters = _build_traffic_filter(supi)
    assert len(filters) == 2
    assert dodo1_validate(filters) == 2


@pytest.mark.parametrize(
    "supi,expected_ul,expected_dl",
    [
        ("imsi-001010070000101", "filter-001-ul", "filter-001-dl"),
        ("imsi-001010070000102", "filter-002-ul", "filter-002-dl"),
        ("imsi-001010070000103", "filter-003-ul", "filter-003-dl"),
        ("imsi-001010070000104", "filter-004-ul", "filter-004-dl"),
    ],
)
def test_pack_filt_id_matches_dodo1_db(supi, expected_ul, expected_dl):
    """SUPI→packFiltId 대응이 두두원 DB 와 일치해야 한다.

    인덱스 기반으로 조인하면 UE2 와 UE3 이 뒤바뀐다 — 회선의 supis 순서가
    [101, 103, 102, 104] 인데 filter 번호는 101→001, 102→002, 103→003 이기 때문이다.
    """
    ul, dl = _build_traffic_filter(supi)
    assert ul.flow_direction == "UPLINK"
    assert dl.flow_direction == "DOWNLINK"
    assert ul.pack_filt_id == expected_ul
    assert dl.pack_filt_id == expected_dl


def test_ue_ip_is_on_the_checked_side():
    """UE IP 가 UPLINK 는 from, DOWNLINK 는 to 에 와야 한다 (뒤집으면 400)."""
    ul, dl = _build_traffic_filter("imsi-001010070000101")
    ue_ip = "192.168.101.10"

    assert DODO1_FLOW_RX.search(ul.flow_description).group(1) == ue_ip
    assert DODO1_FLOW_RX.search(dl.flow_description).group(2) == ue_ip


def test_no_any_to_any_fallback_for_unknown_supi():
    """매핑에 없는 SUPI 는 필터를 만들지 않는다.

    예전에는 `permit in ip from any to any` + crc32 packFiltId 로 폴백했는데,
    두두원 2026-09-22 빌드가 그 본문을 구독 전체 400 으로 거절한다. 조용한 400 보다
    빈 목록 + ERROR 로그가 낫다.
    """
    filters = _build_traffic_filter("imsi-999999999999999")
    assert filters == []


def test_mock_supi_keeps_legacy_behavior():
    """mockup SUPI 는 기존 flowInfo→crc32 경로를 그대로 유지해야 한다.

    mock NF 는 필터를 검증하지 않으므로(nsmf-server 는 len(upf_events) 만 본다)
    이 경로를 바꿀 이유가 없다. HANDOFF §8 「mock 코어 정합성」 회귀 방지.
    """
    filters = _build_traffic_filter("imsi-001010000000001")
    assert len(filters) == 2
    ul, dl = filters
    assert ul.flow_direction == "UPLINK"
    assert dl.flow_direction == "DOWNLINK"
    # crc32 기반이라 순수 숫자 문자열이다
    assert ul.pack_filt_id.isdigit()
    assert dl.pack_filt_id.isdigit()
    # 두두원 형식(filter-00N-xl)이 아니어야 한다 — 섞이면 안 된다
    assert not ul.pack_filt_id.startswith("filter-")


def test_any_ue_path_unchanged():
    """use_any_ue=True (RICF WLAN_PERFORMANCE → 두두원 7p) 는 검증을 타지 않는다.

    이 경로는 오늘 200 을 받고 있으므로 기존 동작을 유지한다.
    """
    filters = _build_traffic_filter("imsi-001010070000101", True)
    assert len(filters) == 2
    assert all(f.flow_description == "permit in ip from any to any" for f in filters)


def test_regression_old_crc_value_would_fail():
    """회귀 감시: 예전 폴백값이 두두원 검증에 걸린다는 사실 자체를 고정한다."""
    old_rule = "permit in ip from any to any"
    assert DODO1_FLOW_RX.search(old_rule) is None
    assert "3902242897" not in DODO1_TRAFFIC_FILTER_SETTING
