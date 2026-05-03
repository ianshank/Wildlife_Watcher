from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from wildlife_ml.export.vela import (
    VelaSummary,
    assert_minimum_npu_coverage,
    build_vela_command,
    parse_vela_report,
    run_vela,
)

_GOOD_REPORT = """
NPU operator coverage: 99.20%
Total cycles: 1,234,567
Total MACs: 9,876,543
"""

_BAD_REPORT = """
Some unrelated text without the expected fields.
"""


def test_parse_vela_report_extracts_fields() -> None:
    summary = parse_vela_report(_GOOD_REPORT)
    assert summary.npu_coverage_percent == pytest.approx(99.2)
    assert summary.cycles == 1_234_567
    assert summary.macs == 9_876_543


def test_parse_vela_report_unexpected_format_raises() -> None:
    with pytest.raises(ValueError, match="Unexpected Vela report format"):
        parse_vela_report(_BAD_REPORT)


def test_assert_minimum_npu_coverage_pass() -> None:
    summary = VelaSummary(npu_coverage_percent=98.0, cycles=1, macs=1)
    # Should not raise
    assert_minimum_npu_coverage(summary, minimum_percent=95.0)


def test_assert_minimum_npu_coverage_fail() -> None:
    summary = VelaSummary(npu_coverage_percent=80.0, cycles=1, macs=1)
    with pytest.raises(ValueError, match="below the floor"):
        assert_minimum_npu_coverage(summary, minimum_percent=95.0)


def test_build_vela_command_default_accelerator(tmp_path: Path) -> None:
    cmd = build_vela_command(tmp_path / "model.tflite", tmp_path / "out")
    assert cmd[0] == "vela"
    assert "--accelerator-config=ethos-u55-128" in cmd
    assert any(p.startswith("--output-dir=") for p in cmd)


def test_build_vela_command_custom_accelerator(tmp_path: Path) -> None:
    cmd = build_vela_command(
        tmp_path / "m.tflite",
        tmp_path / "out",
        accelerator_config="ethos-u65-256",
    )
    assert "--accelerator-config=ethos-u65-256" in cmd


def test_run_vela_dry_run_logs_command_and_returns_zero(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="wildlife_ml.export.vela"):
        rc = run_vela(tmp_path / "m.tflite", tmp_path / "out", dry_run=True)
    assert rc == 0
    assert "vela" in caplog.text
    assert "--accelerator-config=ethos-u55-128" in caplog.text


def test_run_vela_invokes_subprocess_when_not_dry_run(tmp_path: Path) -> None:
    fake = mock.Mock(returncode=42)
    with mock.patch.object(subprocess, "run", return_value=fake) as run_spy:
        rc = run_vela(tmp_path / "m.tflite", tmp_path / "out")
    assert rc == 42
    run_spy.assert_called_once()
