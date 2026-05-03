from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
from wildlife_ml.export import onnx as onnx_mod
from wildlife_ml.export.onnx import (
    OnnxExportConfig,
    build_export_command,
    main,
    prepare_image_batch,
    run_export,
)


def _solid_image(h: int, w: int, value: int = 200) -> np.ndarray:
    return np.full((h, w, 3), value, dtype=np.uint8)


def test_prepare_image_batch_default_config_shape_and_dtype() -> None:
    img = _solid_image(640, 480)
    out = prepare_image_batch(img)
    assert out.shape == (1, 3, 320, 320)
    assert out.dtype == np.float32
    # Values normalised to [0, 1]
    assert 0.0 <= out.min() <= out.max() <= 1.0


def test_prepare_image_batch_custom_config_dimensions() -> None:
    img = _solid_image(120, 160)
    cfg = OnnxExportConfig(image_size=(64, 96))
    out = prepare_image_batch(img, cfg)
    assert out.shape == (1, 3, 64, 96)


def test_prepare_image_batch_rejects_non_hxwx3() -> None:
    with pytest.raises(ValueError, match="HxWx3"):
        prepare_image_batch(np.zeros((10, 10), dtype=np.uint8))


def test_prepare_image_batch_rejects_non_uint8() -> None:
    with pytest.raises(ValueError, match="uint8"):
        prepare_image_batch(np.zeros((10, 10, 3), dtype=np.float32))


def test_build_export_command_contents(tmp_path: Path) -> None:
    cmd = build_export_command(tmp_path / "best.pt", tmp_path / "out")
    assert cmd[0:3] == ["yolo", "export", f"model={tmp_path / 'best.pt'}"]
    assert "format=onnx" in cmd
    assert "imgsz=320,320" in cmd
    assert "opset=13" in cmd


def test_build_export_command_with_custom_config(tmp_path: Path) -> None:
    cfg = OnnxExportConfig(image_size=(192, 320), opset=17)
    cmd = build_export_command(tmp_path / "w.pt", tmp_path / "o", cfg)
    assert "imgsz=192,320" in cmd
    assert "opset=17" in cmd


def test_run_export_dry_run(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="wildlife_ml.export.onnx"):
        rc = run_export(tmp_path / "w.pt", tmp_path / "o", dry_run=True)
    assert rc == 0
    assert "yolo" in caplog.text
    assert "format=onnx" in caplog.text


def test_run_export_invokes_subprocess(tmp_path: Path) -> None:
    fake = mock.Mock(returncode=7)
    with mock.patch.object(subprocess, "run", return_value=fake):
        rc = run_export(tmp_path / "w.pt", tmp_path / "o")
    assert rc == 7


def test_main_invokes_run_export_with_argparse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    weights = tmp_path / "best.pt"
    out = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv",
        ["onnx", "--weights-path", str(weights), "--output-dir", str(out), "--dry-run"],
    )
    sentinel = mock.Mock(return_value=99)
    monkeypatch.setattr(onnx_mod, "run_export", sentinel)
    rc = main()
    assert rc == 99
    sentinel.assert_called_once_with(weights, out, dry_run=True)
