from __future__ import annotations

import pytest
from wildlife_ml.export.vela import (
    assert_minimum_npu_coverage,
    parse_vela_report,
)


def test_parse_vela_report_extracts_summary() -> None:
    report = """
    NPU operator coverage: 97.3%
    Total cycles: 1,234,567
    Total MACs: 345,678
    """
    summary = parse_vela_report(report)
    assert summary.npu_coverage_percent == pytest.approx(97.3)
    assert summary.cycles == 1234567
    assert summary.macs == 345678


def test_assert_minimum_npu_coverage_rejects_low_coverage() -> None:
    report = """
    NPU operator coverage: 70.0%
    Total cycles: 10
    Total MACs: 20
    """
    summary = parse_vela_report(report)
    with pytest.raises(ValueError):
        assert_minimum_npu_coverage(summary, minimum_percent=95.0)
