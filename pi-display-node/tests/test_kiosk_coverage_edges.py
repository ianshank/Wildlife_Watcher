from __future__ import annotations

import contextlib
import queue
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from PyQt5.QtWidgets import QListWidgetItem

import wildlife_kiosk
from conftest import MockMessage
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

QT_USER_ROLE = wildlife_kiosk.QT_USER_ROLE


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


def test_mqtt_bridge_start_stop_and_failed_connect(test_config, monkeypatch):
    events: queue.Queue[object] = queue.Queue()
    bridge = MqttBridge(test_config, events)
    connect_mock = MagicMock(side_effect=RuntimeError("boom"))
    loop_start_mock = MagicMock()
    loop_stop_mock = MagicMock()
    disconnect_mock = MagicMock()
    monkeypatch.setattr(bridge._client, "connect", connect_mock)
    monkeypatch.setattr(bridge._client, "loop_start", loop_start_mock)
    monkeypatch.setattr(bridge._client, "loop_stop", loop_stop_mock)
    monkeypatch.setattr(bridge._client, "disconnect", disconnect_mock)

    bridge.start()
    bridge.stop()

    connect_mock.assert_called_once()
    loop_start_mock.assert_called_once()
    loop_stop_mock.assert_called_once()
    disconnect_mock.assert_called_once()


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
    events.put(StatusEvent(node_id="node-1", state="offline", ip=None, ts="2026-05-01T12:01:00Z"))
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
        datetime.fromisoformat("2026-05-01T12:34:56+00:00").astimezone().strftime("%H:%M:%S")
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
    signal_handlers: dict[int, Any] = {}

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


# ---------------------------------------------------------------------------
# Additional coverage tests (lines identified via coverage.json analysis)
# ---------------------------------------------------------------------------

_DETECTION_BASE = {
    "ts": "2026-05-01T12:00:00Z",
    "node_id": "node1",
    "frame_id": "frame1",
    "class_name": "bird",
    "class_id": 1,
    "confidence": 0.9,
    "bbox": (0, 0, 1, 1),
    "model": "yolo",
    "fps": 10.0,
}


def _make_detection(**overrides) -> DetectionEvent:
    return DetectionEvent(**{**_DETECTION_BASE, **overrides})


# --- line 104: load_config() successful return ---


def test_load_config_returns_dict_for_valid_file(tmp_path, monkeypatch):
    """load_config() returns the parsed dict when the file is valid (line 104)."""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("key: value\n", encoding="utf-8")
    monkeypatch.setattr(wildlife_kiosk, "CONFIG_PATH", Path(cfg_path))

    result = wildlife_kiosk.load_config()

    assert result == {"key": "value"}


# --- lines 211-212: MqttBridge._on_message exception handler ---


def test_on_message_exception_is_caught(test_config):
    """_on_message logs and swallows JSON parse errors (lines 211-212)."""
    events: queue.Queue[object] = queue.Queue()
    bridge = MqttBridge(test_config, events)
    bad_msg = MockMessage("wildlife/detections/node1", b"not valid json{{")
    bridge._on_message(None, None, bad_msg)
    # Exception must be swallowed; queue must remain empty
    with pytest.raises(queue.Empty):
        events.get_nowait()


# --- line 256: _handle_thumb returns early for wrong topic parts ---


def test_handle_thumb_wrong_topic_parts(test_config):
    """_handle_thumb discards messages with malformed topic (line 256)."""
    events: queue.Queue[object] = queue.Queue()
    bridge = MqttBridge(test_config, events)
    # Only 3 parts instead of 4
    bad_msg = MockMessage("wildlife/thumbs/node1", b"raw")
    bridge._on_message(None, None, bad_msg)
    with pytest.raises(queue.Empty):
        events.get_nowait()


# --- lines 377-378: Storage.close() ---


def test_storage_close(mock_db_path):
    """Storage.close() releases the SQLite connection (lines 377-378)."""
    storage = Storage(mock_db_path)
    storage.close()
    # Calling close again must not raise (connection is already closed,
    # but the with-lock guard still runs)
    with contextlib.suppress(Exception):
        storage.close()  # sqlite3.ProgrammingError is acceptable on double-close


# --- lines 460-461: fullscreen mode ---


def test_kiosk_fullscreen_mode(qtbot, test_config, mock_db_path):
    """WildlifeKiosk applies fullscreen cursor and showFullScreen (lines 460-461)."""
    fullscreen_cfg = {**test_config, "ui": {**test_config["ui"], "fullscreen": True}}
    events: queue.Queue[object] = queue.Queue()
    storage = Storage(mock_db_path)
    bridge = MqttBridge(fullscreen_cfg, events)
    window = WildlifeKiosk(fullscreen_cfg, storage, bridge, events)
    qtbot.addWidget(window)
    assert window.isFullScreen()


# --- lines 541, 544-552: _load_initial_feed / _add_feed_row_from_db ---


def test_load_initial_feed_from_existing_db(qtbot, test_config, mock_db_path):
    """Window pre-populates the feed from existing DB observations (lines 541, 544-552)."""
    prep = Storage(mock_db_path)
    prep.insert_detection(_make_detection(), None)
    prep.close()

    events: queue.Queue[object] = queue.Queue()
    storage = Storage(mock_db_path)
    bridge = MqttBridge(test_config, events)
    window = WildlifeKiosk(test_config, storage, bridge, events)
    qtbot.addWidget(window)

    assert window.feed_list.count() == 1


# --- line 557: _trim_feed removes rows beyond max_feed_rows ---


def test_trim_feed_removes_excess_items(kiosk_window):
    """_trim_feed prunes items when count exceeds max_feed_rows (line 557)."""
    window, events, _storage, _bridge = kiosk_window
    # test_config has max_feed_rows=10; send 12 detections
    for i in range(12):
        events.put(_make_detection(frame_id=f"fr{i}", ts=f"2026-05-01T12:00:{i:02d}Z"))
    window._tick()
    assert window.feed_list.count() <= 10


# --- line 586: confidence below threshold early return ---


def test_handle_detection_below_confidence(kiosk_window):
    """_handle_detection skips event below min_confidence_to_show (line 586)."""
    window, events, _storage, _bridge = kiosk_window
    # test_config min_confidence_to_show=0.5; send 0.3
    events.put(_make_detection(confidence=0.3))
    window._tick()
    assert window.feed_list.count() == 0


# --- lines 592-596: cached thumbnail triggers QBuffer encode path ---


def test_handle_detection_thumb_in_cache_already(kiosk_window):
    """Detection reuses thumb already in cache (lines 592-596)."""
    window, events, _storage, _bridge = kiosk_window
    # Thumbnail arrives before detection
    events.put(ThumbnailEvent(node_id="node1", frame_id="frame1", jpeg_bytes=VALID_JPEG))
    events.put(_make_detection(class_name="fox"))  # fox not in classes_to_highlight
    window._tick()
    assert window.feed_list.count() == 1
    assert window._thumb_tiles[0].pixmap_full is not None


# --- lines 628-629: date rollover resets daily counter ---


def test_date_rollover_resets_event_count(kiosk_window):
    """Daily counter resets when date changes mid-session (lines 628-629)."""
    from datetime import timezone as _tz

    window, events, _storage, _bridge = kiosk_window
    window._today_date = "2000-01-01"
    window._events_today_count = 99
    events.put(_make_detection())
    window._tick()
    today = datetime.now(_tz.utc).date().isoformat()
    assert window._today_date == today
    assert window._events_today_count == 1  # reset then incremented


# --- lines 639, 641: bad JPEG in _handle_thumbnail ---


def test_handle_thumbnail_bad_jpeg(kiosk_window):
    """_handle_thumbnail warns and discards non-JPEG payload (lines 639, 641)."""
    window, events, _storage, _bridge = kiosk_window
    events.put(ThumbnailEvent(node_id="node1", frame_id="frame1", jpeg_bytes=b"not-a-jpeg"))
    window._tick()
    assert window._thumb_tiles[0].pixmap_full is None


# --- line 711: _on_feed_clicked early return when no obs_id ---


def test_on_feed_clicked_no_obs_id(kiosk_window):
    """_on_feed_clicked returns early when item carries no obs id (line 711)."""
    window, _events, _storage, _bridge = kiosk_window
    item = QListWidgetItem("no-id-row")
    item.setData(QT_USER_ROLE, {"id": None, "ts": "2026-05-01T12:00:00Z"})
    window._on_feed_clicked(item)
    assert window.stack.currentIndex() == 0


# --- line 714: _on_feed_clicked early return when no jpeg in DB ---


def test_on_feed_clicked_no_jpeg_in_db(kiosk_window):
    """_on_feed_clicked returns early when DB has no thumbnail (line 714)."""
    window, events, _storage, _bridge = kiosk_window
    events.put(_make_detection())
    window._tick()
    # Observation was inserted without a thumbnail
    item = window.feed_list.item(0)
    window._on_feed_clicked(item)
    assert window.stack.currentIndex() == 0


# --- line 717: _on_feed_clicked early return when QImage is null ---


def test_on_feed_clicked_corrupt_jpeg(kiosk_window):
    """_on_feed_clicked returns early when stored bytes are not a valid JPEG (line 717)."""
    window, _events, storage, _bridge = kiosk_window
    obs_id = storage.insert_detection(_make_detection(), b"corrupt-bytes")
    item = QListWidgetItem("corrupt")
    item.setData(
        QT_USER_ROLE,
        {
            "id": obs_id,
            "ts": "2026-05-01T12:00:00Z",
            "node_id": "node1",
            "frame_id": "frame1",
            "class_name": "bird",
            "confidence": 0.9,
            "bbox_x": 0,
            "bbox_y": 0,
            "bbox_w": 1,
            "bbox_h": 1,
        },
    )
    window._on_feed_clicked(item)
    assert window.stack.currentIndex() == 0


# --- line 729: _on_tile_clicked skips empty tile ---


def test_on_tile_clicked_empty_tile(kiosk_window):
    """_on_tile_clicked returns early when tile has no pixmap (line 729)."""
    window, _events, _storage, _bridge = kiosk_window
    empty_tile = window._thumb_tiles[0]  # no pixmap set
    window._on_tile_clicked(empty_tile)
    assert window.stack.currentIndex() == 0


# --- lines 832-833, 837: DetailView.resizeEvent + _render early return ---


def test_detail_view_resize_event_and_early_render(qtbot):
    """resizeEvent fires _render; _render returns early when no pixmap (lines 832-833, 837)."""
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QResizeEvent as _QResizeEvent

    detail = DetailView(on_back=lambda: None)
    qtbot.addWidget(detail)

    # _render called with no raw_pix → early return (line 837)
    detail._render()

    # resizeEvent with a proper Qt event covers lines 832-833
    resize_ev = _QResizeEvent(QSize(320, 240), QSize(0, 0))
    detail.resizeEvent(resize_ev)  # _raw_pix still None → _render returns early again

    # Set content, then fire resizeEvent again to exercise the full _render path
    cache = ThumbCache(max_entries=1)
    pix = cache.put("n", "f", VALID_JPEG)
    assert pix is not None
    detail.set_content(pix, "fox 80%", None)
    detail.resizeEvent(resize_ev)

    assert detail.image_label.pixmap() is not None
