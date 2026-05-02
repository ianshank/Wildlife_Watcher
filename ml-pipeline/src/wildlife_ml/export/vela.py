from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VelaSummary:
    npu_coverage_percent: float
    cycles: int
    macs: int


def parse_vela_report(report_text: str) -> VelaSummary:
    coverage_match = re.search(r"NPU\s+operator\s+coverage:\s+([0-9.]+)%", report_text)
    cycles_match = re.search(r"Total\s+cycles:\s+([0-9,]+)", report_text)
    macs_match = re.search(r"Total\s+MACs:\s+([0-9,]+)", report_text)
    if coverage_match is None or cycles_match is None or macs_match is None:
        raise ValueError("Unexpected Vela report format")
    return VelaSummary(
        npu_coverage_percent=float(coverage_match.group(1)),
        cycles=int(cycles_match.group(1).replace(",", "")),
        macs=int(macs_match.group(1).replace(",", "")),
    )


def assert_minimum_npu_coverage(summary: VelaSummary, minimum_percent: float = 95.0) -> None:
    if summary.npu_coverage_percent < minimum_percent:
        raise ValueError(
            "NPU coverage "
            f"{summary.npu_coverage_percent:.2f}% is below the floor of "
            f"{minimum_percent:.2f}%"
        )


def build_vela_command(
    tflite_model: Path,
    output_dir: Path,
    *,
    accelerator_config: str = "ethos-u55-128",
) -> list[str]:
    return [
        "vela",
        str(tflite_model),
        f"--accelerator-config={accelerator_config}",
        f"--output-dir={output_dir}",
    ]


def run_vela(tflite_model: Path, output_dir: Path, *, dry_run: bool = False) -> int:
    command = build_vela_command(tflite_model, output_dir)
    if dry_run:
        print(" ".join(str(part) for part in command))
        return 0
    completed = subprocess.run(command, check=False)
    return completed.returncode