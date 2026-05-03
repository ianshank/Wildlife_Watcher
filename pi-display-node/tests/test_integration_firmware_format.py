from __future__ import annotations

import base64
import queue
import re
from pathlib import Path

import pytest

from conftest import MockMessage
from test_thumb_cache import VALID_JPEG
from wildlife_kiosk import MqttBridge, ThumbnailEvent

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
FIRMWARE_CONFIG_PATH = (
    REPO_ROOT / "phase2" / "camera-node-firmware" / "include" / "wildlife" / "config.h"
)


def _parse_firmware_macro(name: str) -> str:
    source = FIRMWARE_CONFIG_PATH.read_text(encoding="utf-8")
    pattern = re.compile(rf"#define\s+{re.escape(name)}\s+(.+)")
    match = pattern.search(source)
    if match is None:
        raise AssertionError(f"Could not find firmware macro {name}")
    return match.group(1).strip()


def _thumbs_topic_root() -> str:
    return _parse_firmware_macro("WILDLIFE_THUMBS_TOPIC_ROOT").strip('"')


def _max_thumb_bytes() -> int:
    return int(_parse_firmware_macro("WILDLIFE_MAX_THUMB_BYTES").removesuffix("U"))


def _max_thumb_payload_bytes() -> int:
    raw_budget = _max_thumb_bytes()
    return ((raw_budget + 2) // 3) * 4


def test_firmware_thumb_topic_and_payload_round_trip(test_config) -> None:
    events: queue.Queue[object] = queue.Queue()
    bridge = MqttBridge(test_config, events)
    node_id = "phase2-node"
    frame_id = "f_000123"
    topic = f"{_thumbs_topic_root()}/{node_id}/{frame_id}"
    encoded_thumb = base64.b64encode(VALID_JPEG)

    assert len(encoded_thumb) <= _max_thumb_payload_bytes()

    bridge._on_message(None, None, MockMessage(topic, encoded_thumb))

    event = events.get_nowait()
    assert isinstance(event, ThumbnailEvent)
    assert event.node_id == node_id
    assert event.frame_id == frame_id
    assert event.jpeg_bytes == VALID_JPEG
