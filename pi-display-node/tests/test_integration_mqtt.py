from __future__ import annotations

import base64
import json
import queue
from typing import Any

import pytest

from test_thumb_cache import VALID_JPEG
from wildlife_kiosk import MqttBridge, Storage, WildlifeKiosk

pytestmark = pytest.mark.integration

# Topic roots are pinned by pi-display-node/kiosk/config.yaml
# (wildlife/{detections,status,thumbs}/+) and the firmware-side macros in
# phase2/camera-node-firmware/include/wildlife/config.h. Centralising them
# here keeps the integration tests in lock-step with that contract; if either
# side drifts, the schema/parity tests already fail loudly.
STATUS_TOPIC = "wildlife/status/{node_id}"
DETECTIONS_TOPIC = "wildlife/detections/{node_id}"
THUMBS_TOPIC = "wildlife/thumbs/{node_id}/{frame_id}"


def _detection_payload(
    *,
    frame_id: str,
    timestamp: str,
    class_id: int = 0,
    class_name: str = "bird",
    confidence: float = 0.97,
    bbox: tuple[int, int, int, int] = (11, 22, 33, 44),
    model: str = "ethos-u55",
    fps: float = 7.5,
) -> bytes:
    payload: dict[str, Any] = {
        "ts": timestamp,
        "frame_id": frame_id,
        "model": model,
        "fps": fps,
        "detections": [
            {
                "class_id": class_id,
                "class_name": class_name,
                "confidence": confidence,
                "bbox": list(bbox),
            }
        ],
    }
    return json.dumps(payload).encode("utf-8")


def _status_payload(*, ip: str, timestamp: str, state: str = "online") -> bytes:
    return json.dumps({"state": state, "ip": ip, "ts": timestamp}).encode("utf-8")


def _publish_status(publisher, *, node_id: str, ip: str, timestamp: str) -> None:
    info = publisher.publish(
        STATUS_TOPIC.format(node_id=node_id),
        _status_payload(ip=ip, timestamp=timestamp),
        qos=1,
        retain=True,
    )
    info.wait_for_publish(timeout=5)


def _publish_detection(publisher, *, node_id: str, payload: bytes) -> None:
    info = publisher.publish(DETECTIONS_TOPIC.format(node_id=node_id), payload, qos=1)
    info.wait_for_publish(timeout=5)


def _publish_thumb(publisher, *, node_id: str, frame_id: str, jpeg_bytes: bytes) -> None:
    info = publisher.publish(
        THUMBS_TOPIC.format(node_id=node_id, frame_id=frame_id),
        base64.b64encode(jpeg_bytes),
        qos=0,
    )
    info.wait_for_publish(timeout=5)


def _observation_landed(storage, window, *, node_id: str, frame_id: str) -> bool:
    recent = storage.recent_observations(1)
    if len(recent) != 1:
        return False
    row = recent[0]
    if row["node_id"] != node_id or row["frame_id"] != frame_id:
        return False
    if storage.thumb_for(row["id"]) != VALID_JPEG:
        return False
    return window.thumb_cache.get(node_id, frame_id) is not None


@pytest.fixture
def kiosk_integration_app(qtbot, broker_test_config, mock_db_path):
    events: queue.Queue[object] = queue.Queue()
    storage = Storage(mock_db_path)
    bridge = MqttBridge(broker_test_config, events)
    window = WildlifeKiosk(broker_test_config, storage, bridge, events)
    qtbot.addWidget(window)

    bridge.start()
    qtbot.waitUntil(lambda: bridge.connected, timeout=5000)

    yield window, storage, bridge, broker_test_config

    bridge.stop()
    window.close()
    storage.close()


def test_kiosk_processes_embedded_broker_messages(
    kiosk_integration_app, broker_publisher, qtbot
) -> None:
    window, storage, _bridge, _cfg = kiosk_integration_app
    node_id = "broker-node"
    frame_id = "frame-001"
    ip = "192.168.1.42"

    _publish_status(broker_publisher, node_id=node_id, ip=ip, timestamp="2026-05-03T12:00:00Z")
    qtbot.waitUntil(lambda: node_id in window.online_nodes, timeout=5000)

    _publish_detection(
        broker_publisher,
        node_id=node_id,
        payload=_detection_payload(frame_id=frame_id, timestamp="2026-05-03T12:00:01Z"),
    )
    _publish_thumb(broker_publisher, node_id=node_id, frame_id=frame_id, jpeg_bytes=VALID_JPEG)

    qtbot.waitUntil(
        lambda: _observation_landed(storage, window, node_id=node_id, frame_id=frame_id),
        timeout=5000,
    )

    recent = storage.recent_observations(1)
    assert len(recent) == 1
    row = recent[0]
    assert row["node_id"] == node_id
    assert row["frame_id"] == frame_id
    assert row["class_name"] == "bird"
    assert storage.thumb_for(row["id"]) == VALID_JPEG
    assert window.thumb_cache.get(node_id, frame_id) is not None
    assert window.online_nodes[node_id]["ip"] == ip
    assert window.feed_list.count() == 1


def test_kiosk_drops_malformed_detection_payload(
    kiosk_integration_app, broker_publisher, qtbot
) -> None:
    """Scenario S5 from docs/08-integration-e2e-plan.md.

    A malformed detection payload must not crash the bridge or write a row,
    and a subsequent valid detection on the same connection must still flow
    through to storage and the thumbnail cache.
    """

    window, storage, _bridge, _cfg = kiosk_integration_app
    node_id = "malformed-node"
    frame_id = "frame-good-001"
    ip = "192.168.1.43"

    _publish_status(broker_publisher, node_id=node_id, ip=ip, timestamp="2026-05-03T12:10:00Z")
    qtbot.waitUntil(lambda: node_id in window.online_nodes, timeout=5000)

    # Bad payload: invalid JSON bytes. MqttBridge._on_message catches
    # JSONDecodeError and logs it; the kiosk must not write a row.
    bad_publish = broker_publisher.publish(
        DETECTIONS_TOPIC.format(node_id=node_id), b"{not-json", qos=1
    )
    bad_publish.wait_for_publish(timeout=5)
    qtbot.wait(300)

    assert storage.recent_observations(1) == []
    assert window.feed_list.count() == 0

    # Same connection must still process a well-formed detection + thumb.
    _publish_detection(
        broker_publisher,
        node_id=node_id,
        payload=_detection_payload(
            frame_id=frame_id, timestamp="2026-05-03T12:10:01Z", confidence=0.91
        ),
    )
    _publish_thumb(broker_publisher, node_id=node_id, frame_id=frame_id, jpeg_bytes=VALID_JPEG)

    qtbot.waitUntil(
        lambda: _observation_landed(storage, window, node_id=node_id, frame_id=frame_id),
        timeout=5000,
    )

    recent = storage.recent_observations(1)
    assert len(recent) == 1
    assert recent[0]["frame_id"] == frame_id
    assert window.feed_list.count() == 1
