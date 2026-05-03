"""Hardware-In-the-Loop integration tests for the camera node firmware.

These tests require the XIAO ESP32S3 Sense + Grove Vision AI V2 to be
physically connected.  The embedded MQTT broker (amqtt) is started
automatically by conftest.py, so no external Mosquitto is needed.

Test categories:
  - Infrastructure tests: verify WiFi/MQTT connectivity (always pass
    if the hardware is powered and credentials are correct).
  - Detection tests: require the camera to actually "see" a subject.
    Marked with @pytest.mark.detection so they can be skipped via
    ``pytest -m "not detection"`` when running in an empty room.
  - Edge-case / resilience tests: verify the firmware handles
    unusual conditions gracefully.
"""
from __future__ import annotations

import base64
import json
import time

import paho.mqtt.client as mqtt
import pytest

from conftest import BROKER_HOST, BROKER_PORT, NODE_ID

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATUS_TOPIC = f"wildlife/status/{NODE_ID}"
DETECTION_TOPIC = f"wildlife/detections/{NODE_ID}"
THUMBS_PREFIX = f"wildlife/thumbs/{NODE_ID}/"


def _drain_until(msg_queue, topic_prefix, timeout, predicate=None):
    """Drain messages until one matching topic_prefix (and optional predicate) appears."""
    start = time.time()
    collected = []
    while time.time() - start < timeout:
        if not msg_queue.empty():
            msg = msg_queue.get()
            if msg.topic.startswith(topic_prefix):
                collected.append(msg)
                if predicate is None or predicate(msg):
                    return collected, msg
        time.sleep(0.05)
    return collected, None


# ===========================================================================
# Infrastructure tests — always pass if hardware is connected
# ===========================================================================


def test_boot_status(mqtt_client):
    """Device connects to WiFi + MQTT and publishes 'online' status."""
    _, msg_queue = mqtt_client

    _, match = _drain_until(msg_queue, STATUS_TOPIC, timeout=30)
    assert match is not None, (
        "Did not receive any status message within 30 seconds."
    )

    payload = json.loads(match.payload.decode("utf-8"))
    assert payload["state"] == "online"
    assert "ip" in payload, "Status payload missing 'ip' field"
    assert "uptime_ms" in payload, "Status payload missing 'uptime_ms'"
    assert "node_id" in payload, "Status payload missing 'node_id'"
    assert payload["node_id"] == NODE_ID


def test_status_topic_is_retained(mqtt_client):
    """The status message should be published with the retained flag.

    A new subscriber joining after boot should immediately receive the
    last known state without waiting for the next heartbeat.
    """
    import queue as _queue

    late_queue: _queue.Queue[mqtt.MQTTMessage] = _queue.Queue()

    def on_msg(_c, _u, msg):
        late_queue.put(msg)

    # Create a second "late joiner" client
    late = mqtt.Client(client_id="pytest-late-joiner", clean_session=True)
    late.on_message = on_msg
    late.connect(BROKER_HOST, BROKER_PORT, 60)
    late.subscribe(STATUS_TOPIC)
    late.loop_start()

    try:
        _, match = _drain_until(late_queue, STATUS_TOPIC, timeout=5)
        assert match is not None, (
            "Late-joining subscriber did not receive retained status. "
            "Is the firmware publishing with retained=true?"
        )
        payload = json.loads(match.payload.decode("utf-8"))
        assert payload["state"] == "online"
    finally:
        late.loop_stop()
        late.disconnect()


def test_heartbeat_interval(mqtt_client):
    """Heartbeats arrive at roughly HEARTBEAT_MS (30 s) intervals.

    The first few status messages may arrive rapidly (retained replay +
    on-connect publish), so we skip the first 2 and measure between the
    2nd and 3rd to get a true heartbeat interval.
    """
    _, msg_queue = mqtt_client

    timestamps: list[float] = []
    start = time.time()
    while time.time() - start < 90 and len(timestamps) < 3:
        if not msg_queue.empty():
            msg = msg_queue.get()
            if msg.topic == STATUS_TOPIC:
                try:
                    p = json.loads(msg.payload.decode("utf-8"))
                    if p.get("state") == "online":
                        timestamps.append(time.time())
                except json.JSONDecodeError:
                    pass
        time.sleep(0.05)

    assert len(timestamps) >= 3, (
        f"Only received {len(timestamps)} heartbeat(s) in 90 s (need 3)."
    )
    # Measure interval between 2nd and 3rd (skipping retained/connect burst)
    delta = timestamps[2] - timestamps[1]
    assert 15 <= delta <= 50, (
        f"Heartbeat interval {delta:.1f}s is outside expected 15-50s window."
    )


def test_topic_structure(mqtt_client):
    """All messages from the device follow the wildlife/<type>/<node_id> contract."""
    _, msg_queue = mqtt_client

    allowed_prefixes = (
        f"wildlife/status/{NODE_ID}",
        f"wildlife/detections/{NODE_ID}",
        f"wildlife/thumbs/{NODE_ID}/",
    )

    start = time.time()
    violations = []
    checked = 0
    while time.time() - start < 15:
        if not msg_queue.empty():
            msg = msg_queue.get()
            checked += 1
            if not any(msg.topic.startswith(p) for p in allowed_prefixes):
                violations.append(msg.topic)
        time.sleep(0.05)

    assert checked > 0, "No messages received in 15 s — is the device running?"
    assert not violations, (
        f"Unexpected topic(s): {violations}"
    )


def test_status_payload_ip_is_valid(mqtt_client):
    """The 'ip' field in the status payload is a valid IPv4 address."""
    import ipaddress

    _, msg_queue = mqtt_client

    _, match = _drain_until(msg_queue, STATUS_TOPIC, timeout=30)
    assert match is not None
    payload = json.loads(match.payload.decode("utf-8"))
    ip_str = payload.get("ip", "")
    try:
        addr = ipaddress.IPv4Address(ip_str)
    except ipaddress.AddressValueError:
        pytest.fail(f"'{ip_str}' is not a valid IPv4 address")
    # Should not be 0.0.0.0 or loopback
    assert not addr.is_loopback, f"IP is loopback: {addr}"
    assert str(addr) != "0.0.0.0", "IP is 0.0.0.0 — WiFi likely not connected"


def test_uptime_increases(mqtt_client):
    """Two consecutive status messages show increasing uptime_ms."""
    _, msg_queue = mqtt_client

    uptimes = []
    start = time.time()
    while time.time() - start < 70 and len(uptimes) < 2:
        if not msg_queue.empty():
            msg = msg_queue.get()
            if msg.topic == STATUS_TOPIC:
                try:
                    p = json.loads(msg.payload.decode("utf-8"))
                    if "uptime_ms" in p:
                        uptimes.append(p["uptime_ms"])
                except json.JSONDecodeError:
                    pass
        time.sleep(0.05)

    assert len(uptimes) >= 2, "Need at least 2 status messages for comparison"
    assert uptimes[1] > uptimes[0], (
        f"uptime_ms did not increase: {uptimes[0]} -> {uptimes[1]}. "
        "Possible reboot mid-test?"
    )


# ===========================================================================
# Detection tests — require visual stimuli in front of the camera
# ===========================================================================


@pytest.mark.detection
def test_detections_published(mqtt_client):
    """Camera detects a subject and publishes valid detection JSON."""
    _, msg_queue = mqtt_client

    print(
        "\n[test] Waiting for a detection… "
        "Place a subject in front of the camera!"
    )

    _, match = _drain_until(
        msg_queue, DETECTION_TOPIC, timeout=60,
        predicate=lambda m: len(
            json.loads(m.payload).get("detections", [])
        ) > 0,
    )

    assert match is not None, (
        "Did not receive any detections within 60s. Does it see anything?"
    )

    payload = json.loads(match.payload.decode("utf-8"))
    assert "ts" in payload
    assert "frame_id" in payload
    assert payload["model"] == "grove_vision_ai_v2"
    assert isinstance(payload["fps"], (int, float))
    assert payload["fps"] >= 0

    det = payload["detections"][0]
    assert isinstance(det["class_id"], int)
    assert isinstance(det["class_name"], str) and len(det["class_name"]) > 0
    assert 0.0 <= det["confidence"] <= 1.0
    assert len(det["bbox"]) == 4
    assert all(isinstance(v, (int, float)) for v in det["bbox"])


@pytest.mark.detection
def test_confidence_range(mqtt_client):
    """All reported confidences are in [0.0, 1.0] (firmware divides by 100)."""
    _, msg_queue = mqtt_client

    detections_checked = 0
    start = time.time()
    while time.time() - start < 60:
        if not msg_queue.empty():
            msg = msg_queue.get()
            if msg.topic == DETECTION_TOPIC:
                payload = json.loads(msg.payload.decode("utf-8"))
                for det in payload.get("detections", []):
                    conf = det["confidence"]
                    assert 0.0 <= conf <= 1.0, (
                        f"confidence {conf} outside [0,1] — "
                        "firmware may not be dividing by 100"
                    )
                    detections_checked += 1
                if detections_checked >= 3:
                    break
        time.sleep(0.05)

    assert detections_checked >= 1, "No detections received to validate"


@pytest.mark.detection
def test_frame_ids_are_sequential(mqtt_client):
    """frame_id values increase monotonically across detection messages."""
    _, msg_queue = mqtt_client

    frame_ids = []
    start = time.time()
    while time.time() - start < 60 and len(frame_ids) < 5:
        if not msg_queue.empty():
            msg = msg_queue.get()
            if msg.topic == DETECTION_TOPIC:
                payload = json.loads(msg.payload.decode("utf-8"))
                fid = payload.get("frame_id", "")
                # frame_id format is "f_000001"
                if fid.startswith("f_"):
                    frame_ids.append(int(fid.split("_")[1]))
        time.sleep(0.05)

    assert len(frame_ids) >= 2, "Need at least 2 detections to check ordering"
    for i in range(1, len(frame_ids)):
        assert frame_ids[i] > frame_ids[i - 1], (
            f"frame_id not monotonically increasing: {frame_ids}"
        )


@pytest.mark.detection
def test_class_debounce(mqtt_client):
    """Same class_id should not re-fire within CLASS_DEBOUNCE_MS (2 s).

    Collect detections and verify no duplicate class_id appears with
    less than ~1.5 s between them (allowing some margin).
    """
    _, msg_queue = mqtt_client

    # class_id -> list of wall-clock timestamps
    class_times: dict[int, list[float]] = {}
    start = time.time()
    while time.time() - start < 30:
        if not msg_queue.empty():
            msg = msg_queue.get()
            if msg.topic == DETECTION_TOPIC:
                payload = json.loads(msg.payload.decode("utf-8"))
                now = time.time()
                for det in payload.get("detections", []):
                    cid = det["class_id"]
                    class_times.setdefault(cid, []).append(now)
        time.sleep(0.05)

    violations = []
    for cid, times in class_times.items():
        for i in range(1, len(times)):
            delta = times[i] - times[i - 1]
            if delta < 1.5:
                violations.append((cid, f"{delta:.2f}s"))

    assert not violations, (
        f"Debounce violated for class(es): {violations}. "
        "Expected >= 2 s between same class_id."
    )


@pytest.mark.detection
def test_thumbnail_published(mqtt_client):
    """Camera publishes a valid JPEG thumbnail after a detection.

    The firmware publishes base64-encoded JPEGs.  We try base64 first,
    then fall back to raw binary.  Timeout is 120 s because save_jpeg()
    only fires when confidence >= THUMB_PUBLISH_THRESHOLD.
    """
    _, msg_queue = mqtt_client

    start_time = time.time()
    thumb_seen = False

    while time.time() - start_time < 120:
        if not msg_queue.empty():
            msg = msg_queue.get()
            if msg.topic.startswith(THUMBS_PREFIX):
                payload = bytes(msg.payload)
                try:
                    jpeg_bytes = base64.b64decode(payload, validate=True)
                except Exception:
                    jpeg_bytes = payload

                if jpeg_bytes.startswith(b"\xff\xd8\xff"):
                    # Verify it also ends with JPEG EOI marker
                    assert jpeg_bytes[-2:] == b"\xff\xd9", (
                        "JPEG missing EOI marker — possibly truncated"
                    )
                    thumb_seen = True
                    break
                else:
                    print(
                        f"[test] Thumb payload ({len(jpeg_bytes)} B) "
                        f"not JPEG (magic: {jpeg_bytes[:4].hex()})"
                    )
        time.sleep(0.1)

    assert thumb_seen, (
        "Did not receive a valid JPEG thumbnail within 120 seconds."
    )


@pytest.mark.detection
def test_thumbnail_topic_contains_frame_id(mqtt_client):
    """Thumbnail topic includes a frame_id matching a recent detection."""
    _, msg_queue = mqtt_client

    known_frame_ids: set[str] = set()
    matched = False
    start = time.time()

    while time.time() - start < 60:
        if not msg_queue.empty():
            msg = msg_queue.get()
            if msg.topic == DETECTION_TOPIC:
                payload = json.loads(msg.payload.decode("utf-8"))
                fid = payload.get("frame_id", "")
                if fid:
                    known_frame_ids.add(fid)
            elif msg.topic.startswith(THUMBS_PREFIX):
                thumb_frame_id = msg.topic.split("/")[-1]
                if thumb_frame_id in known_frame_ids:
                    matched = True
                    break
        time.sleep(0.05)

    assert matched, (
        f"No thumbnail's frame_id matched a known detection. "
        f"Known: {known_frame_ids}"
    )


# ===========================================================================
# Edge-case / resilience tests
# ===========================================================================


def test_broker_reconnect(mqtt_client):
    """Device reconnects to broker after a brief MQTT disconnect.

    We publish a fake 'kick' by disconnecting our client and
    reconnecting — then verify the device is still publishing.
    This doesn't actually disconnect the *device*, but it validates
    that the broker continues to relay after client churn.
    """
    client, msg_queue = mqtt_client

    # Disconnect and reconnect our subscriber
    client.disconnect()
    time.sleep(2)
    client.reconnect()
    client.subscribe("wildlife/#")
    time.sleep(1)

    # Device should still be publishing heartbeats
    _, match = _drain_until(msg_queue, STATUS_TOPIC, timeout=35)
    assert match is not None, (
        "No status message after subscriber reconnect — "
        "broker may have dropped the device session."
    )


def test_no_crash_under_sustained_load(mqtt_client):
    """Device remains stable over a 60 s observation window.

    We count total messages and verify no gaps > 35 s (heartbeat
    interval + margin), which would indicate a crash or reboot.
    """
    _, msg_queue = mqtt_client

    messages = 0
    last_msg_time = time.time()
    start = time.time()
    max_gap = 0.0

    while time.time() - start < 60:
        if not msg_queue.empty():
            msg = msg_queue.get()
            now = time.time()
            gap = now - last_msg_time
            if gap > max_gap:
                max_gap = gap
            last_msg_time = now
            messages += 1
        time.sleep(0.05)

    assert messages >= 2, (
        f"Only {messages} message(s) in 60 s — device may have crashed."
    )
    assert max_gap < 35, (
        f"Largest gap between messages was {max_gap:.1f}s (> 35s). "
        "Device may have rebooted."
    )
