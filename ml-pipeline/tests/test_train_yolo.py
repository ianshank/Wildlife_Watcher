from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from wildlife_ml.train.yolo import TrainConfig, build_training_command, run_training


def _config(tmp_path: Path) -> TrainConfig:
    return TrainConfig(
        dataset_yaml=tmp_path / "dataset.yaml",
        output_dir=tmp_path / "runs",
    )


def test_build_training_command_contains_required_keys(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cmd = build_training_command(cfg)
    assert cmd[:3] == ["yolo", "detect", "train"]
    assert f"data={cfg.dataset_yaml}" in cmd
    assert f"project={cfg.output_dir}" in cmd
    assert f"model={cfg.model_name}" in cmd
    assert f"epochs={cfg.epochs}" in cmd
    assert f"imgsz={cfg.image_size}" in cmd
    assert f"batch={cfg.batch_size}" in cmd
    assert f"device={cfg.device}" in cmd


def test_build_training_command_default_hyperparams(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    assert cfg.model_name == "yolov8n.pt"
    assert cfg.epochs == 50
    assert cfg.image_size == 320
    assert cfg.batch_size == 16
    assert cfg.device == "cpu"


def test_build_training_command_custom_hyperparams(tmp_path: Path) -> None:
    cfg = TrainConfig(
        dataset_yaml=tmp_path / "ds.yaml",
        output_dir=tmp_path / "out",
        model_name="yolov8s.pt",
        epochs=100,
        image_size=640,
        batch_size=32,
        device="0",
    )
    cmd = build_training_command(cfg)
    assert "model=yolov8s.pt" in cmd
    assert "epochs=100" in cmd
    assert "imgsz=640" in cmd
    assert "batch=32" in cmd
    assert "device=0" in cmd


def test_run_training_dry_run_logs_and_returns_zero(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = _config(tmp_path)
    with caplog.at_level(logging.INFO, logger="wildlife_ml.train.yolo"):
        rc = run_training(cfg, dry_run=True)
    assert rc == 0
    assert "yolo" in caplog.text
    assert "detect" in caplog.text
    assert "train" in caplog.text


def test_run_training_dry_run_does_not_invoke_subprocess(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with mock.patch.object(subprocess, "run") as run_spy:
        run_training(cfg, dry_run=True)
    run_spy.assert_not_called()


def test_run_training_invokes_subprocess_when_not_dry_run(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    fake = mock.Mock(returncode=0)
    with mock.patch.object(subprocess, "run", return_value=fake) as run_spy:
        rc = run_training(cfg)
    assert rc == 0
    run_spy.assert_called_once()


def test_run_training_propagates_subprocess_returncode(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    fake = mock.Mock(returncode=1)
    with mock.patch.object(subprocess, "run", return_value=fake):
        rc = run_training(cfg)
    assert rc == 1
