import queue

import pytest

from test_thumb_cache import VALID_JPEG
from wildlife_kiosk import (
    DetectionEvent,
    MqttBridge,
    StatusEvent,
    Storage,
    ThumbnailEvent,
    WildlifeKiosk,
)


@pytest.fixture
def kiosk_app(qtbot, test_config, mock_db_path):
    events = queue.Queue()
    storage = Storage(mock_db_path)
    bridge = MqttBridge(test_config, events)

    window = WildlifeKiosk(test_config, storage, bridge, events)
    qtbot.addWidget(window)
    return window, events, storage


def test_kiosk_initialization(kiosk_app):
    window, _events, _storage = kiosk_app
    assert window.windowTitle() == "Wildlife Watcher"
    assert window.feed_list.count() == 0


def test_kiosk_handle_detection(kiosk_app):
    window, events, storage = kiosk_app

    ev = DetectionEvent(
        ts="2026-05-01T12:00:00Z",
        node_id="node1",
        frame_id="frame1",
        class_name="bird",
        class_id=1,
        confidence=0.9,
        bbox=(10, 10, 100, 100),
        model="yolo",
        fps=10.0,
    )
    events.put(ev)
    window._tick()  # Process queue

    # Verify UI updated
    assert window.feed_list.count() == 1
    item = window.feed_list.item(0)
    assert "bird" in item.text()
    assert "node1" in item.text()

    # Verify DB updated
    recent = storage.recent_observations(1)
    assert len(recent) == 1
    assert recent[0]["frame_id"] == "frame1"


def test_kiosk_handle_thumbnail(kiosk_app):
    window, events, _storage = kiosk_app

    # First detection
    ev_det = DetectionEvent(
        ts="2026-05-01T12:00:00Z",
        node_id="node1",
        frame_id="frame1",
        class_name="bird",
        class_id=1,
        confidence=0.9,
        bbox=(10, 10, 100, 100),
        model="yolo",
        fps=10.0,
    )
    events.put(ev_det)

    # Then thumbnail
    ev_thumb = ThumbnailEvent(node_id="node1", frame_id="frame1", jpeg_bytes=VALID_JPEG)
    events.put(ev_thumb)

    window._tick()

    # Verify thumbnail tile is populated
    tile = window._thumb_tiles[0]
    assert tile.pixmap_full is not None
    assert "bird" in tile.caption_text
    assert "node1" in tile.caption_text


def test_kiosk_handle_status(kiosk_app):
    window, events, _storage = kiosk_app

    ev = StatusEvent(node_id="node1", state="online", ip="192.168.1.100", ts="2026-05-01T12:00:00Z")
    events.put(ev)
    window._tick()

    assert "node1" in window.online_nodes
    header_text = window.header_label.text()
    assert "connected" in header_text or "DISCONNECTED" in header_text
    assert "node1" in window.header_label.text()


def test_kiosk_detail_view(kiosk_app):
    window, events, _storage = kiosk_app

    # Push item to grid
    ev_thumb = ThumbnailEvent(node_id="node1", frame_id="frame1", jpeg_bytes=VALID_JPEG)
    events.put(ev_thumb)
    window._tick()

    tile = window._thumb_tiles[0]

    # Simulate clicking
    tile.clicked.emit(tile)

    # Should switch to detail page (index 1)
    assert window.stack.currentIndex() == 1

    # Go back
    window.detail_page.findChild(type(window.detail_page.layout().itemAt(2).widget())).click()
    assert window.stack.currentIndex() == 0
