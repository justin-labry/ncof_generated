# DEVICE 모드의 NF 정보 파일 로딩을 검증하는 테스트
import json

import pytest

from nncof.core import nrf as nrf_module


def test_build_device_nfs_reads_device_info(monkeypatch, tmp_path):
    expected = {
        "SMF": {
            "base_uri": "http://device-smf:9001",
            "services": {"nsmf-eventexposure": ""},
        }
    }
    device_info_file = tmp_path / "device_info.json"
    device_info_file.write_text(json.dumps(expected), encoding="utf-8")
    monkeypatch.setattr(
        nrf_module,
        "_find_upwards",
        lambda filename: str(device_info_file) if filename == "device_info.json" else None,
    )

    assert nrf_module._build_device_nfs() == expected


def test_build_device_nfs_requires_device_info(monkeypatch):
    monkeypatch.setattr(nrf_module, "_find_upwards", lambda filename: None)

    with pytest.raises(FileNotFoundError, match="device_info.json"):
        nrf_module._build_device_nfs()


def test_build_device_nfs_requires_json_object(monkeypatch, tmp_path):
    device_info_file = tmp_path / "device_info.json"
    device_info_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(nrf_module, "_find_upwards", lambda filename: str(device_info_file))

    with pytest.raises(ValueError, match="최상위 값은 객체"):
        nrf_module._build_device_nfs()
