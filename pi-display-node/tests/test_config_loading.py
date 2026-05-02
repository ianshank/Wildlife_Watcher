from pathlib import Path

import pytest

import wildlife_kiosk


def test_load_config_rejects_non_mapping(tmp_path, monkeypatch):
    config_path = tmp_path / "bad-config.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    monkeypatch.setattr(wildlife_kiosk, "CONFIG_PATH", Path(config_path))

    with pytest.raises(SystemExit) as excinfo:
        wildlife_kiosk.load_config()

    assert excinfo.value.code == 2
