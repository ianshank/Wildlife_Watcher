import base64
import json
import queue
from unittest.mock import MagicMock

import pytest

from conftest import MockMessage
from wildlife_kiosk import DetectionEvent, MqttBridge, StatusEvent, ThumbnailEvent


def test_mqtt_bridge_detection(test_config):
    events = queue.Queue()
    bridge = MqttBridge(test_config, events)

    payload = {
        "ts": "2026-05-01T12:00:00Z",
        "frame_id": "frame1",
        "model": "yolo",
        "fps": 15.5,
        "detections": [
            {
                "class_id": 1,
                "class_name": "bird",
                "confidence": 0.95,
                "bbox": [10, 20, 30, 40]
            }
        ]
    }
    msg = MockMessage("wildlife/detections/node1", json.dumps(payload).encode("utf-8"))
    bridge._on_message(None, None, msg)

    ev = events.get_nowait()
    assert isinstance(ev, DetectionEvent)
    assert ev.node_id == "node1"
    assert ev.frame_id == "frame1"
    assert ev.class_name == "bird"
    assert ev.confidence == 0.95
    assert ev.bbox == (10, 20, 30, 40)
    assert ev.fps == 15.5


def test_mqtt_bridge_detection_skips_invalid_bbox(test_config):
    events = queue.Queue()
    bridge = MqttBridge(test_config, events)

    payload = {
        "ts": "2026-05-01T12:00:00Z",
        "frame_id": "frame1",
        "detections": [
            {
                "class_id": 1,
                "class_name": "bird",
                "confidence": 0.95,
                "bbox": [10, 20, 30],
            }
        ],
    }
    msg = MockMessage("wildlife/detections/node1", json.dumps(payload).encode("utf-8"))
    bridge._on_message(None, None, msg)

    with pytest.raises(queue.Empty):
        events.get_nowait()

def test_mqtt_bridge_thumb(test_config):
    events = queue.Queue()
    bridge = MqttBridge(test_config, events)

    # Send raw bytes
    msg = MockMessage("wildlife/thumbs/node1/frame1", b"raw_jpeg_data")
    bridge._on_message(None, None, msg)

    ev = events.get_nowait()
    assert isinstance(ev, ThumbnailEvent)
    assert ev.node_id == "node1"
    assert ev.frame_id == "frame1"
    assert ev.jpeg_bytes == b"raw_jpeg_data"


def test_mqtt_bridge_thumb_decodes_base64(test_config):
    events = queue.Queue()
    bridge = MqttBridge(test_config, events)

    payload = base64.b64encode(b"jpeg_bytes")
    msg = MockMessage("wildlife/thumbs/node1/frame1", payload)
    bridge._on_message(None, None, msg)

    ev = events.get_nowait()
    assert isinstance(ev, ThumbnailEvent)
    assert ev.jpeg_bytes == b"jpeg_bytes"

def test_mqtt_bridge_status(test_config):
    events = queue.Queue()
    bridge = MqttBridge(test_config, events)

    payload = {
        "state": "online",
        "ip": "192.168.1.50",
        "ts": "2026-05-01T12:00:00Z"
    }
    msg = MockMessage("wildlife/status/node1", json.dumps(payload).encode("utf-8"))
    bridge._on_message(None, None, msg)

    ev = events.get_nowait()
    assert isinstance(ev, StatusEvent)
    assert ev.node_id == "node1"
    assert ev.state == "online"
    assert ev.ip == "192.168.1.50"


def test_mqtt_bridge_status_plain_text_fallback(test_config):
    events = queue.Queue()
    bridge = MqttBridge(test_config, events)

    msg = MockMessage("wildlife/status/node1", b"offline")
    bridge._on_message(None, None, msg)

    ev = events.get_nowait()
    assert isinstance(ev, StatusEvent)
    assert ev.node_id == "node1"
    assert ev.state == "offline"
    assert ev.ip is None

def test_mqtt_bridge_connect_disconnect(test_config):
    events = queue.Queue()
    bridge = MqttBridge(test_config, events)

    mock_client = MagicMock()
    bridge._on_connect(mock_client, None, None, 0)
    assert bridge.connected is True

    bridge._on_disconnect(mock_client, None, 0)
    assert bridge.connected is False
