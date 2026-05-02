from __future__ import annotations

import queue
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import wildlife_kiosk
from test_thumb_cache import VALID_JPEG
from wildlife_kiosk import (
    DetailView,
    DetectionEvent,
    MqttBridge,
    StatusEvent,
    Storage,
    ThumbCache,
    ThumbnailEvent,
    ThumbTile,
    WildlifeKiosk,
)


@pytest.fixture
def kiosk_window(qtbot, test_config, mock_db_path):
    events: queue.Queue[object] = queue.Queue()
    storage = Storage(mock_db_path)
    bridge = MqttBridge(test_config, events)
    window = WildlifeKiosk(test_config, storage, bridge, events)
    qtbot.addWidget(window)
    return window, events, storage, bridge


def test_load_config_exits_when_file_is_missing(tmp_path, monkeypatch):
    missing_path = tmp_path / "missing-config.yaml"
    monkeypatch.setattr(wildlife_kiosk, "CONFIG_PATH", Path(missing_path))

    with pytest.raises(SystemExit) as excinfo:
        wildlife_kiosk.load_config()

    assert excinfo.value.code == 2


def test_mqtt_bridge_start_stop_and_failed_connect(test_config):
    events: queue.Queue[object] = queue.Queue()
    bridge = MqttBridge(test_config, events)
    bridge._client.connect = MagicMock(side_effect=RuntimeError("boom"))
    bridge._client.loop_start = MagicMock()
    bridge._client.loop_stop = MagicMock()
    bridge._client.disconnect = MagicMock()

    bridge.start()
    bridge.stop()

    bridge._client.connect.assert_called_once()
    bridge._client.loop_start.assert_called_once()
    bridge._client.loop_stop.assert_called_once()
    bridge._client.disconnect.assert_called_once()


def test_mqtt_bridge_on_connect_nonzero_rc_does_not_subscribe(test_config):
    events: queue.Queue[object] = queue.Queue()
    bridge = MqttBridge(test_config, events)
    client = MagicMock()

    bridge._on_connect(client, None, None, 5)

    assert bridge.connected is False
    client.subscribe.assert_not_called()


def test_tick_handles_exceptions_and_offline_status(kiosk_window, monkeypatch):
    window, events, storage, _bridge = kiosk_window
    del storage
    events.put(object())
    monkeypatch.setattr(window, "_handle_event", MagicMock(side_effect=RuntimeError("bad event")))

    window._tick()
    assert "Broker:" in window.header_label.text()
    assert "DB:" in window.footer_label.text()

    events.put(
        StatusEvent(node_id="node-1", state="online", ip="1.2.3.4", ts="2026-05-01T12:00:00Z")
    )
    events.put(
        StatusEvent(node_id="node-1", state="offline", ip=None, ts="2026-05-01T12:01:00Z")
    )
    monkeypatch.undo()
    window._tick()

    assert "node-1" not in window.online_nodes


def test_feed_click_and_show_main_with_thumbnail(kiosk_window):
    window, events, _storage, _bridge = kiosk_window
    detection = DetectionEvent(
        ts="2026-05-01T12:00:00Z",
        node_id="node1",
        frame_id="frame1",
        class_name="bird",
        class_id=1,
        confidence=0.91,
        bbox=(10, 20, 30, 40),
        model="yolo",
        fps=10.0,
    )
    thumb = ThumbnailEvent(node_id="node1", frame_id="frame1", jpeg_bytes=VALID_JPEG)
    events.put(detection)
    events.put(thumb)

    window._tick()
    item = window.feed_list.item(0)
    window._on_feed_clicked(item)

    assert window.stack.currentIndex() == 1
    window._show_main()
    assert window.stack.currentIndex() == 0


def test_thumb_tile_copy_from_and_click(qtbot):
    cache = ThumbCache(max_entries=1)
    pix = cache.put("node-1", "frame-1", VALID_JPEG)
    assert pix is not None

    source = ThumbTile()
    target = ThumbTile()
    empty = ThumbTile()
    qtbot.addWidget(source)
    qtbot.addWidget(target)
    qtbot.addWidget(empty)

    source.set_thumb(
        pix,
        "node-1",
        "frame-1",
        {
            "class_name": "bird",
            "confidence": 0.8,
            "bbox_x": 1,
            "bbox_y": 2,
            "bbox_w": 3,
            "bbox_h": 4,
        },
    )
    target.copy_from(source)
    assert target.caption.text() == source.caption.text()
    assert target.bbox == source.bbox

    target.copy_from(empty)
    assert target.pixmap_full is None
    assert target.caption.text() == "—"

    seen: list[ThumbTile] = []
    target.clicked.connect(seen.append)
    target.mousePressEvent(None)
    assert seen == [target]


def test_detail_view_render_and_timestamp_helpers(qtbot):
    detail = DetailView(on_back=lambda: None)
    qtbot.addWidget(detail)
    detail.resize(320, 240)
    cache = ThumbCache(max_entries=1)
    pix = cache.put("node-1", "frame-1", VALID_JPEG)
    assert pix is not None

    detail.set_content(pix, "bird 80% · node-1", (0, 0, 1, 1))

    assert detail.caption.text() == "bird 80% · node-1"
    assert detail.image_label.pixmap() is not None
    expected_short = (
        datetime.fromisoformat("2026-05-01T12:34:56+00:00")
        .astimezone()
        .strftime("%H:%M:%S")
    )
    assert wildlife_kiosk._short_ts("2026-05-01T12:34:56Z") == expected_short
    assert wildlife_kiosk._short_ts("") == "        "
    assert wildlife_kiosk._short_ts("not-a-ts") == "not-a-ts"
    assert wildlife_kiosk._now_iso().endswith("Z")


def test_main_starts_components_and_registers_shutdown(monkeypatch, tmp_path):
    db_path = tmp_path / "observations.db"
    cfg = {
        "storage": {"db_path": str(db_path), "retain_days": 30},
        "mqtt": {
            "client_id": "test-client",
            "host": "localhost",
            "port": 1883,
            "keepalive": 60,
            "username": "test",
            "password": "test",
            "topics": {
                "detections": "wildlife/detections/+",
                "thumbs": "wildlife/thumbs/+/+",
                "status": "wildlife/status/+",
            },
        },
        "ui": {
            "fullscreen": False,
            "thumb_grid_cols": 2,
            "thumb_grid_rows": 2,
            "max_feed_rows": 10,
            "min_confidence_to_show": 0.0,
            "refresh_ms": 100,
            "classes_to_highlight": ["bird"],
        },
    }

    fake_storage = MagicMock()
    fake_storage.db_path = db_path
    fake_storage.purge_old.return_value = 3
    fake_bridge = MagicMock()
    fake_window = MagicMock()

    class FakeApp:
        def __init__(self):
            self.quit = MagicMock()
            self.setApplicationName = MagicMock()

        def exec_(self):
            return 0

    fake_app = FakeApp()
    signal_handlers = {}

    monkeypatch.setattr(wildlife_kiosk, "load_config", lambda: cfg)
    monkeypatch.setattr(wildlife_kiosk, "Storage", lambda path: fake_storage)
    monkeypatch.setattr(
        wildlife_kiosk,
        "MqttBridge",
        lambda loaded_cfg, event_q: fake_bridge,
    )
    monkeypatch.setattr(
        wildlife_kiosk,
        "WildlifeKiosk",
        lambda loaded_cfg, storage, bridge, event_q: fake_window,
    )
    monkeypatch.setattr(wildlife_kiosk, "QApplication", lambda argv: fake_app)
    monkeypatch.setattr(
        wildlife_kiosk.signal,
        "signal",
        lambda sig, handler: signal_handlers.setdefault(sig, handler),
    )

    assert wildlife_kiosk.main() == 0
    fake_bridge.start.assert_called_once()
    fake_window.show.assert_called_once()
    fake_app.setApplicationName.assert_called_once_with("Wildlife Watcher")
    assert wildlife_kiosk.signal.SIGTERM in signal_handlers
    assert wildlife_kiosk.signal.SIGINT in signal_handlers

    signal_handlers[wildlife_kiosk.signal.SIGTERM]()
    fake_bridge.stop.assert_called_once()
    fake_storage.close.assert_called_once()
    fake_app.quit.assert_called_once()
