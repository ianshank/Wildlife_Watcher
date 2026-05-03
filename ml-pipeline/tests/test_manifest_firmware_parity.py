from __future__ import annotations

import json
import re
from pathlib import Path

from wildlife_ml.export.manifest import ExportManifest


REPO_ROOT = Path(__file__).resolve().parents[2]
FIRMWARE_CONFIG_PATH = (
    REPO_ROOT
    / "phase2"
    / "camera-node-firmware"
    / "include"
    / "wildlife"
    / "config.h"
)
MANIFEST_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "export_manifest.json"


def _parse_firmware_class_names() -> tuple[str, ...]:
    source = FIRMWARE_CONFIG_PATH.read_text(encoding="utf-8")
    marker = "#define WILDLIFE_CLASS_NAMES \\\n"
    macro_body = source.split(marker, maxsplit=1)[1].split("#endif", maxsplit=1)[0]
    return tuple(re.findall(r'"([^"]+)"', macro_body))


def _load_manifest_fixture() -> ExportManifest:
    payload = json.loads(MANIFEST_FIXTURE_PATH.read_text(encoding="utf-8"))
    return ExportManifest(
        model_path=Path(payload["model_path"]),
        class_names=tuple(payload["class_names"]),
        image_size=tuple(payload["image_size"]),
        opset=int(payload["opset"]),
    )


def test_export_manifest_fixture_matches_firmware_class_table() -> None:
    manifest = _load_manifest_fixture()
    firmware_class_names = _parse_firmware_class_names()

    assert firmware_class_names
    assert manifest.class_names == firmware_class_names
    assert len(manifest.class_names) == len(firmware_class_names)