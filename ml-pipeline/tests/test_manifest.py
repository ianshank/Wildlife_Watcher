from __future__ import annotations

from pathlib import Path

import pytest
from wildlife_ml.export.manifest import ExportManifest
from wildlife_ml.export.onnx import OnnxExportConfig


def test_manifest_round_trip() -> None:
    cfg = OnnxExportConfig(image_size=(416, 416), opset=17)
    m = ExportManifest.from_config(
        model_path=Path("model.onnx"),
        class_names=("bird", "cat", "dog"),
        config=cfg,
    )
    assert m.model_path == Path("model.onnx")
    assert m.class_names == ("bird", "cat", "dog")
    assert m.image_size == (416, 416)
    assert m.opset == 17


def test_manifest_rejects_empty_class_names() -> None:
    with pytest.raises(ValueError, match="class_names must not be empty"):
        ExportManifest(
            model_path=Path("model.onnx"),
            class_names=(),
            image_size=(320, 320),
            opset=13,
        )


def test_manifest_image_size_comes_from_config() -> None:
    cfg = OnnxExportConfig(image_size=(224, 224))
    m = ExportManifest.from_config(
        model_path=Path("weights.onnx"),
        class_names=("bird",),
        config=cfg,
    )
    assert m.image_size == cfg.image_size


def test_manifest_normalizes_dynamic_class_name_inputs() -> None:
    m = ExportManifest.from_config(
        model_path=Path("weights.onnx"),
        class_names=["bird", "fox"],
    )
    assert m.class_names == ("bird", "fox")


def test_manifest_to_dict_is_serialization_friendly() -> None:
    m = ExportManifest.from_config(
        model_path=Path("weights.onnx"),
        class_names=("bird", "fox"),
        config=OnnxExportConfig(image_size=(224, 128), opset=17),
    )
    assert m.to_dict() == {
        "model_path": "weights.onnx",
        "class_names": ["bird", "fox"],
        "image_size": [224, 128],
        "opset": 17,
    }


def test_manifest_rejects_blank_class_names() -> None:
    with pytest.raises(ValueError, match="class_names must contain non-empty labels"):
        ExportManifest.from_config(
            model_path=Path("weights.onnx"),
            class_names=("bird", "  "),
        )


def test_manifest_to_summary_format() -> None:
    cfg = OnnxExportConfig(image_size=(320, 320), opset=13)
    m = ExportManifest.from_config(
        model_path=Path('m.onnx'),
        class_names=('bird', 'cat'),
        config=cfg,
    )
    s = m.to_summary()
    assert 'm.onnx' in s
    assert 'bird, cat' in s
    assert '320x320' in s
    assert 'opset=13' in s

