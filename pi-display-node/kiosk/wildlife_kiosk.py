#!/usr/bin/env python3
"""
wildlife_kiosk.py — Touchscreen kiosk for the Wildlife Watcher display node.

Runs on Raspberry Pi Zero 2 W with a Waveshare 7" 1024x600 capacitive touch
display. Subscribes to MQTT topics produced by camera nodes (Grove Vision AI
V2 + XIAO ESP32S3 Sense), persists detections to SQLite, and renders a live
event feed and thumbnail grid suitable for poking at with a finger.

Architecture notes:
  - paho.mqtt runs in its own thread; it pushes events into a thread-safe
    queue. The Qt main thread polls the queue on a QTimer (no signals from
    background thread, which simplifies things and avoids edge cases with
    PyQt5 signal/slot across thread boundaries on this hardware).
  - SQLite writes happen on the Qt thread, batched per refresh tick. This is
    fine for the data rates we expect (a busy feeder might produce 30 events
    per minute, which is 0.5 events/sec — trivial).
  - Thumbnails are kept in-memory (LRU-ish cache, 100 entries) and also
    persisted as BLOBs in the observations table. We don't write JPEG files
    to disk in Phase 1 — the SD card is the bottleneck and BLOBs are fine
    for our volumes.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import queue
import signal
import sqlite3
import sys
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import paho.mqtt.client as mqtt
import yaml
from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("wildlife_kiosk")

CONFIG_PATH = Path(os.environ.get("WILDLIFE_CONFIG", "/etc/wildlife/config.yaml"))
_qt_namespace = cast(Any, Qt)
_qiodevice_namespace = cast(Any, QIODevice)

def _compat_qt_value(namespace: Any, scoped_enum: str, value_name: str) -> Any:
    enum_namespace = getattr(namespace, scoped_enum, namespace)
    return getattr(enum_namespace, value_name)


QT_BLANK_CURSOR = _compat_qt_value(_qt_namespace, "CursorShape", "BlankCursor")
QT_USER_ROLE = _compat_qt_value(_qt_namespace, "ItemDataRole", "UserRole")
QT_ALIGN_CENTER = _compat_qt_value(_qt_namespace, "AlignmentFlag", "AlignCenter")
QT_KEEP_ASPECT_RATIO = _compat_qt_value(_qt_namespace, "AspectRatioMode", "KeepAspectRatio")
QT_SMOOTH_TRANSFORMATION = _compat_qt_value(
    _qt_namespace,
    "TransformationMode",
    "SmoothTransformation",
)
QIO_WRITE_ONLY = _compat_qt_value(_qiodevice_namespace, "OpenModeFlag", "WriteOnly")

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        log.error("Config not found at %s", CONFIG_PATH)
        sys.exit(2)
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    if not isinstance(config, dict):
        log.error("Config at %s must contain a top-level mapping", CONFIG_PATH)
        sys.exit(2)
    return cast(dict[str, Any], config)


# ---------------------------------------------------------------------------
# Event types passed from MQTT thread to Qt thread
# ---------------------------------------------------------------------------

@dataclass
class DetectionEvent:
    ts: str
    node_id: str
    frame_id: str
    class_name: str
    class_id: int
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h
    model: str
    fps: float


@dataclass
class ThumbnailEvent:
    node_id: str
    frame_id: str
    jpeg_bytes: bytes


@dataclass
class StatusEvent:
    node_id: str
    state: str          # 'online' or 'offline'
    ip: str | None
    ts: str


# ---------------------------------------------------------------------------
# MQTT bridge — runs in background thread
# ---------------------------------------------------------------------------


def _make_paho_client(client_id: str, *, clean_session: bool = True) -> mqtt.Client:
    """Construct a paho.mqtt.Client that works on both 1.6.x and 2.x.

    paho-mqtt 2.0 added a required ``CallbackAPIVersion`` positional arg.
    Kept inline (rather than imported from ``scripts/``) so the kiosk
    package remains self-contained when installed on the Pi.
    """
    cb_api = getattr(mqtt, "CallbackAPIVersion", None)
    if cb_api is not None:
        try:
            # Use Any-typed alias so mypy doesn't raise on positional/keyword
            # conflicts whose error code varies across paho stub versions.
            _cls: Any = mqtt.Client
            _client = _cls(
                cb_api.VERSION1,
                client_id=client_id,
                clean_session=clean_session,
            )
            return cast(mqtt.Client, _client)
        except TypeError:
            pass
    return mqtt.Client(client_id=client_id, clean_session=clean_session)


class MqttBridge:
    """
    Wraps paho-mqtt with our topic-specific parsing logic. All inbound events
    are pushed into `self.events` (a queue.Queue) for the Qt thread to drain.
    """

    def __init__(self, cfg: dict[str, Any], events: queue.Queue[Any]):
        self.cfg = cfg
        self.events = events
        self._client = _make_paho_client(
            cfg["mqtt"]["client_id"],
            clean_session=True,
        )
        self._client.username_pw_set(
            cfg["mqtt"]["username"], cfg["mqtt"]["password"]
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        self._connected = threading.Event()

    # ------------------------------------------------------------------
    def start(self) -> None:
        try:
            self._client.connect(
                self.cfg["mqtt"]["host"],
                self.cfg["mqtt"]["port"],
                self.cfg["mqtt"]["keepalive"],
            )
        except Exception as exc:
            log.error("MQTT connect failed: %s", exc)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            log.error("MQTT connect rc=%s", rc)
            return
        self._connected.set()
        log.info("MQTT connected")
        topics = self.cfg["mqtt"]["topics"]
        client.subscribe([
            (topics["detections"], 1),
            (topics["thumbs"],     0),
            (topics["status"],     1),
        ])

    def _on_disconnect(self, client, userdata, rc):
        self._connected.clear()
        log.warning("MQTT disconnected rc=%s", rc)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            if topic.startswith("wildlife/detections/"):
                self._handle_detection(topic, msg.payload)
            elif topic.startswith("wildlife/thumbs/"):
                self._handle_thumb(topic, msg.payload)
            elif topic.startswith("wildlife/status/"):
                self._handle_status(topic, msg.payload)
        except (json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError, ValueError):
            log.exception("Failed to handle %s", topic)

    # ------------------------------------------------------------------
    def _handle_detection(self, topic: str, payload: bytes) -> None:
        node_id = topic.rsplit("/", 1)[-1]
        data = json.loads(payload.decode("utf-8"))
        ts        = data.get("ts", _now_iso())
        frame_id  = data.get("frame_id", "")
        model     = data.get("model", "unknown")
        fps       = float(data.get("fps", 0.0))
        for det in data.get("detections", []):
            bbox_raw = det.get("bbox", [0, 0, 0, 0])
            if not isinstance(bbox_raw, (list, tuple)) or len(bbox_raw) < 4:
                log.debug("Skipping detection with invalid bbox from %s: %r", node_id, bbox_raw)
                continue
            bbox = (
                int(bbox_raw[0]),
                int(bbox_raw[1]),
                int(bbox_raw[2]),
                int(bbox_raw[3]),
            )
            self.events.put(DetectionEvent(
                ts=ts,
                node_id=node_id,
                frame_id=frame_id,
                class_name=det.get("class_name", "?"),
                class_id=int(det.get("class_id", -1)),
                confidence=float(det.get("confidence", 0.0)),
                bbox=bbox,
                model=model,
                fps=fps,
            ))
            log.debug(
                "Queued detection node=%s frame=%s class=%s confidence=%.3f",
                node_id,
                frame_id,
                det.get("class_name", "?"),
                float(det.get("confidence", 0.0)),
            )

    def _handle_thumb(self, topic: str, payload: bytes) -> None:
        # Topic: wildlife/thumbs/<node_id>/<frame_id>
        parts = topic.split("/")
        if len(parts) != 4:
            return
        node_id, frame_id = parts[2], parts[3]
        # Payload is base64-encoded JPEG (firmware does this to keep the
        # MQTT message ASCII-safe and easy to inspect with mosquitto_sub).
        try:
            jpeg = base64.b64decode(payload, validate=True)
        except Exception:
            # Fall back to raw bytes — some clients publish binary directly.
            jpeg = bytes(payload)
        self.events.put(ThumbnailEvent(
            node_id=node_id, frame_id=frame_id, jpeg_bytes=jpeg
        ))
        log.debug("Queued thumbnail node=%s frame=%s bytes=%d", node_id, frame_id, len(jpeg))

    def _handle_status(self, topic: str, payload: bytes) -> None:
        node_id = topic.rsplit("/", 1)[-1]
        try:
            data = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            data = {"state": payload.decode("utf-8", errors="ignore").strip()}
        self.events.put(StatusEvent(
            node_id=node_id,
            state=data.get("state", "unknown"),
            ip=data.get("ip"),
            ts=data.get("ts", _now_iso()),
        ))
        log.debug(
            "Queued status node=%s state=%s ip=%s",
            node_id,
            data.get("state"),
            data.get("ip"),
        )


# ---------------------------------------------------------------------------
# Storage layer — SQLite writes happen on the Qt thread
# ---------------------------------------------------------------------------

class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._lock = threading.Lock()

    def insert_detection(self, ev: DetectionEvent, thumb: bytes | None) -> int:
        x, y, w, h = ev.bbox
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO observations
                  (ts, node_id, frame_id, class_name, class_id, confidence,
                   bbox_x, bbox_y, bbox_w, bbox_h, model, fps, thumb_jpeg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ev.ts, ev.node_id, ev.frame_id, ev.class_name, ev.class_id,
                 ev.confidence, x, y, w, h, ev.model, ev.fps, thumb),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def update_thumb(self, node_id: str, frame_id: str, jpeg: bytes) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE observations SET thumb_jpeg = ?
                 WHERE node_id = ? AND frame_id = ? AND thumb_jpeg IS NULL
                """,
                (jpeg, node_id, frame_id),
            )
            self._conn.commit()

    def upsert_node(self, node_id: str, state: str, ip: str | None, ts: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO nodes (node_id, last_seen, last_ip, state)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    last_ip   = COALESCE(excluded.last_ip, nodes.last_ip),
                    state     = excluded.state
                """,
                (node_id, ts, ip, state),
            )
            self._conn.commit()

    def recent_observations(self, limit: int) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(
                """
                SELECT id, ts, node_id, frame_id, class_name, confidence,
                       bbox_x, bbox_y, bbox_w, bbox_h
                  FROM observations
                 ORDER BY ts DESC
                 LIMIT ?
                """,
                (limit,),
            ))

    def thumb_for(self, obs_id: int) -> bytes | None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT thumb_jpeg FROM observations WHERE id = ?",
                (obs_id,),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None

    def purge_old(self, retain_days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retain_days)).isoformat()
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM observations WHERE ts < ?", (cutoff,),
            )
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ---------------------------------------------------------------------------
# Thumbnail cache — keep recent JPEGs hot in RAM
# ---------------------------------------------------------------------------

class ThumbCache:
    def __init__(self, max_entries: int = 100):
        self._max = max_entries
        self._cache: OrderedDict[str, QPixmap] = OrderedDict()

    @staticmethod
    def _key(node_id: str, frame_id: str) -> str:
        return f"{node_id}/{frame_id}"

    def put(self, node_id: str, frame_id: str, jpeg: bytes) -> QPixmap | None:
        img = QImage.fromData(QByteArray(jpeg), "JPEG")
        if img.isNull():
            return None
        pix = QPixmap.fromImage(img)
        key = self._key(node_id, frame_id)
        self._cache[key] = pix
        self._cache.move_to_end(key)
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)
        return pix

    def get(self, node_id: str, frame_id: str) -> QPixmap | None:
        return self._cache.get(self._key(node_id, frame_id))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

CSS = """
QWidget { background-color: #0f1115; color: #e6e9ef; font-family: 'DejaVu Sans'; }
QLabel#header { background-color: #1a1d24; padding: 8px 12px; font-size: 16px; }
QLabel#header[brokerState="ok"] { color: #6ee787; }
QLabel#header[brokerState="warn"] { color: #f0a020; }
QLabel#header[brokerState="error"] { color: #f04848; }
QListWidget { background-color: #14171d; border: 1px solid #2a2f3a; font-size: 13px; }
QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #1f242e; }
QListWidget::item:selected { background-color: #2a3142; }
QFrame#thumbTile { background-color: #14171d; border: 1px solid #2a2f3a; }
QFrame#thumbTile:hover { border: 1px solid #4a90e2; }
QPushButton { background-color: #2a3142; color: #e6e9ef; border: 1px solid #3a4255;
              padding: 8px 16px; font-size: 14px; }
QPushButton:pressed { background-color: #3a4255; }
QLabel#footer { background-color: #1a1d24; padding: 6px 12px; font-size: 12px; color: #9aa0aa; }
QLabel#thumbLabel { background-color: #14171d; }
"""


class WildlifeKiosk(QMainWindow):
    def __init__(
        self,
        cfg: dict[str, Any],
        storage: Storage,
        mqtt_bridge: MqttBridge,
        event_queue: queue.Queue[Any],
    ):
        super().__init__()
        self.cfg = cfg
        self.storage = storage
        self.mqtt = mqtt_bridge
        self.events = event_queue
        self.thumb_cache = ThumbCache(max_entries=120)
        self.online_nodes: dict[str, dict] = {}
        # Track recent obs ids to populate thumbnails after they arrive
        self._frame_to_obs_id: dict[tuple[str, str], int] = {}
        # Stats for footer
        self._events_last_minute: list[datetime] = []
        self._events_today_count = 0
        self._today_date: str = datetime.now(timezone.utc).date().isoformat()

        self.setWindowTitle("Wildlife Watcher")
        self.setStyleSheet(CSS)

        ui = cfg["ui"]
        if ui.get("fullscreen", True):
            self.setCursor(QT_BLANK_CURSOR)
            self.showFullScreen()
        else:
            self.resize(ui["screen_width"], ui["screen_height"])

        self._build_ui()
        self._load_initial_feed()

        # Drive periodic refresh from MQTT queue
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(ui.get("refresh_ms", 250))

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- header ----
        self.header_label = QLabel("Starting up…")
        self.header_label.setObjectName("header")
        self.header_label.setProperty("brokerState", "warn")
        outer.addWidget(self.header_label)

        # ---- main split: stacked widget swaps between feed and detail ----
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, stretch=1)

        # Page 0: feed + thumb grid
        page_main = QWidget()
        h = QHBoxLayout(page_main)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(8)

        # Left: event feed
        self.feed_list = QListWidget()
        self.feed_list.itemClicked.connect(self._on_feed_clicked)
        h.addWidget(self.feed_list, stretch=2)

        # Right: thumbnail grid
        thumb_panel = QWidget()
        self.thumb_grid = QGridLayout(thumb_panel)
        self.thumb_grid.setContentsMargins(0, 0, 0, 0)
        self.thumb_grid.setSpacing(6)
        cols = self.cfg["ui"].get("thumb_grid_cols", 4)
        rows = self.cfg["ui"].get("thumb_grid_rows", 3)
        self._thumb_tiles: list[ThumbTile] = []
        for r in range(rows):
            for c in range(cols):
                tile = ThumbTile()
                tile.clicked.connect(self._on_tile_clicked)
                self._thumb_tiles.append(tile)
                self.thumb_grid.addWidget(tile, r, c)
        h.addWidget(thumb_panel, stretch=3)

        self.stack.addWidget(page_main)

        # Page 1: full-screen detail view
        self.detail_page = DetailView(on_back=self._show_main)
        self.stack.addWidget(self.detail_page)

        # ---- footer ----
        self.footer_label = QLabel("—")
        self.footer_label.setObjectName("footer")
        outer.addWidget(self.footer_label)

    # ------------------------------------------------------------------
    def _show_main(self) -> None:
        self.stack.setCurrentIndex(0)

    def _show_detail(self, pixmap: QPixmap, caption: str, bbox: tuple[Any, ...] | None) -> None:
        self.detail_page.set_content(pixmap, caption, bbox)
        self.stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    def _load_initial_feed(self) -> None:
        rows = self.storage.recent_observations(self.cfg["ui"]["max_feed_rows"])
        for row in rows:
            self._add_feed_row_from_db(row)

    def _add_feed_row_from_db(self, row: sqlite3.Row) -> None:
        ts_short = _short_ts(row["ts"])
        text = (
            f"{ts_short}  {row['class_name']:>8s}  "
            f"{row['confidence']*100:5.1f}%   {row['node_id']}"
        )
        item = QListWidgetItem(text)
        item.setData(QT_USER_ROLE, dict(row))
        self.feed_list.insertItem(0, item)
        self._trim_feed()

    def _trim_feed(self) -> None:
        max_rows = self.cfg["ui"]["max_feed_rows"]
        while self.feed_list.count() > max_rows:
            self.feed_list.takeItem(self.feed_list.count() - 1)

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        # Drain the MQTT event queue
        drained = 0
        while drained < 50:  # avoid blocking the UI on a flood
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            drained += 1
            try:
                self._handle_event(ev)
            except Exception:
                log.exception("Failed handling %r", ev)
        self._refresh_header_footer()

    # ------------------------------------------------------------------
    def _handle_event(self, ev: Any) -> None:
        if isinstance(ev, DetectionEvent):
            self._handle_detection(ev)
        elif isinstance(ev, ThumbnailEvent):
            self._handle_thumbnail(ev)
        elif isinstance(ev, StatusEvent):
            self._handle_status(ev)

    def _handle_detection(self, ev: DetectionEvent) -> None:
        if ev.confidence < self.cfg["ui"].get("min_confidence_to_show", 0.0):
            return
        # Maybe we already have a thumbnail for this frame_id (thumbs sometimes
        # arrive before the detection on a flaky network).
        thumb = None
        cached = self.thumb_cache.get(ev.node_id, ev.frame_id)
        if cached is not None:
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIO_WRITE_ONLY)
            cached.save(buf, "JPEG", quality=70)
            thumb = bytes(ba)

        obs_id = self.storage.insert_detection(ev, thumb)
        if obs_id:
            self._frame_to_obs_id[(ev.node_id, ev.frame_id)] = obs_id

        # Update feed
        ts_short = _short_ts(ev.ts)
        text = (
            f"{ts_short}  {ev.class_name:>8s}  "
            f"{ev.confidence*100:5.1f}%   {ev.node_id}"
        )
        item = QListWidgetItem(text)
        item.setData(QT_USER_ROLE, {
            "id": obs_id, "ts": ev.ts, "node_id": ev.node_id,
            "frame_id": ev.frame_id, "class_name": ev.class_name,
            "confidence": ev.confidence,
            "bbox_x": ev.bbox[0], "bbox_y": ev.bbox[1],
            "bbox_w": ev.bbox[2], "bbox_h": ev.bbox[3],
        })
        if ev.class_name in self.cfg["ui"].get("classes_to_highlight", []):
            f = QFont()
            f.setBold(True)
            item.setFont(f)
            item.setForeground(QColor("#ffd479"))
        self.feed_list.insertItem(0, item)
        self._trim_feed()

        # Stats
        self._events_last_minute.append(datetime.now(timezone.utc))
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self._today_date:
            self._today_date = today
            self._events_today_count = 0
        self._events_today_count += 1

        # If we already have the thumbnail in cache, update the grid
        if cached is not None:
            self._push_thumb_to_grid(ev.node_id, ev.frame_id, cached, ev)

    def _handle_thumbnail(self, ev: ThumbnailEvent) -> None:
        pix = self.thumb_cache.put(ev.node_id, ev.frame_id, ev.jpeg_bytes)
        if pix is None:
            log.warning("Bad JPEG from %s/%s (%d bytes)",
                        ev.node_id, ev.frame_id, len(ev.jpeg_bytes))
            return
        # Persist to DB if the detection row already exists
        self.storage.update_thumb(ev.node_id, ev.frame_id, ev.jpeg_bytes)
        # Find a matching detection in recent feed to attach metadata
        meta = self._lookup_meta(ev.node_id, ev.frame_id)
        self._push_thumb_to_grid(ev.node_id, ev.frame_id, pix, meta)

    def _handle_status(self, ev: StatusEvent) -> None:
        self.storage.upsert_node(ev.node_id, ev.state, ev.ip, ev.ts)
        if ev.state == "online":
            self.online_nodes[ev.node_id] = {"ip": ev.ip, "ts": ev.ts}
        else:
            self.online_nodes.pop(ev.node_id, None)

    # ------------------------------------------------------------------
    def _lookup_meta(self, node_id: str, frame_id: str) -> Any:
        for i in range(min(self.feed_list.count(), 10)):
            item = self.feed_list.item(i)
            if item is None:  # pragma: no cover
                continue
            data = item.data(QT_USER_ROLE)
            if (data and data.get("node_id") == node_id
                    and data.get("frame_id") == frame_id):
                return data
        return None

    def _push_thumb_to_grid(self, node_id: str, frame_id: str,
                            pix: QPixmap, meta: Any) -> None:
        # Shift tiles right, drop oldest
        for i in range(len(self._thumb_tiles) - 1, 0, -1):
            self._thumb_tiles[i].copy_from(self._thumb_tiles[i - 1])
        self._thumb_tiles[0].set_thumb(pix, node_id, frame_id, meta)

    # ------------------------------------------------------------------
    def _refresh_header_footer(self) -> None:
        # Trim events_last_minute to last 60 s
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
        self._events_last_minute = [
            t for t in self._events_last_minute if t > cutoff
        ]

        broker_state = "connected" if self.mqtt.connected else "DISCONNECTED"
        broker_style = "ok" if self.mqtt.connected else "error"
        nodes_str = (
            f"{len(self.online_nodes)} node(s) online: "
            + ", ".join(sorted(self.online_nodes)) if self.online_nodes
            else "no camera nodes online"
        )
        self.header_label.setText(
            f"Wildlife Watcher  ·  Broker: {broker_state}  ·  {nodes_str}"
        )
        if self.header_label.property("brokerState") != broker_style:
            self.header_label.setProperty("brokerState", broker_style)
            style = self.header_label.style()
            if style is not None:
                style.unpolish(self.header_label)
                style.polish(self.header_label)

        rate = len(self._events_last_minute)
        self.footer_label.setText(
            f"Events today: {self._events_today_count}   "
            f"·   {rate} events/min   ·   "
            f"DB: {self.storage.db_path.name}"
        )

    # ------------------------------------------------------------------
    def _on_feed_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(QT_USER_ROLE) or {}
        obs_id = data.get("id")
        if not obs_id:
            return
        jpeg = self.storage.thumb_for(obs_id)
        if not jpeg:
            return
        img = QImage.fromData(QByteArray(jpeg), "JPEG")
        if img.isNull():
            return
        pix = QPixmap.fromImage(img)
        cap = (f"{data.get('class_name','?')}  "
               f"{data.get('confidence',0)*100:.1f}%   "
               f"{data.get('node_id','')}   "
               f"{_short_ts(data.get('ts',''))}")
        bbox = (data.get("bbox_x"), data.get("bbox_y"),
                data.get("bbox_w"), data.get("bbox_h"))
        self._show_detail(pix, cap, bbox)

    def _on_tile_clicked(self, tile: ThumbTile) -> None:
        if tile.pixmap_full is None:
            return
        self._show_detail(tile.pixmap_full, tile.caption_text, tile.bbox)


class ThumbTile(QFrame):
    clicked = pyqtSignal(object)  # emits self

    def __init__(self):
        super().__init__()
        self.setObjectName("thumbTile")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(120, 90)
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(2)
        self.image_label = QLabel()
        self.image_label.setObjectName("thumbLabel")
        self.image_label.setAlignment(QT_ALIGN_CENTER)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.caption = QLabel("—")
        self.caption.setAlignment(QT_ALIGN_CENTER)
        self.caption.setStyleSheet("font-size: 10px; color: #9aa0aa;")
        v.addWidget(self.image_label, stretch=1)
        v.addWidget(self.caption)
        self.pixmap_full: QPixmap | None = None
        self.caption_text: str = ""
        self.bbox: tuple[Any, ...] | None = None
        self._node_id: str = ""
        self._frame_id: str = ""

    def set_thumb(self, pix: QPixmap, node_id: str, frame_id: str, meta: Any) -> None:
        self.pixmap_full = pix
        self._node_id = node_id
        self._frame_id = frame_id
        scaled = pix.scaled(
            self.image_label.size(),
            QT_KEEP_ASPECT_RATIO,
            QT_SMOOTH_TRANSFORMATION,
        )
        self.image_label.setPixmap(scaled)
        if isinstance(meta, dict):
            cls = meta.get("class_name", "?")
            conf = meta.get("confidence", 0)
            self.caption_text = f"{cls} {conf*100:.0f}% · {node_id}"
            self.bbox = (meta.get("bbox_x"), meta.get("bbox_y"),
                         meta.get("bbox_w"), meta.get("bbox_h"))
        else:
            self.caption_text = node_id
            self.bbox = None
        self.caption.setText(self.caption_text)

    def copy_from(self, other: ThumbTile) -> None:
        if other.pixmap_full is None:
            self.pixmap_full = None
            self.image_label.clear()
            self.caption.setText("—")
            self.caption_text = ""
            self.bbox = None
            return
        self.set_thumb(other.pixmap_full, other._node_id, other._frame_id, {
            "class_name": other.caption_text.split()[0] if other.caption_text else "?",
            "confidence": 0,
        })
        self.caption_text = other.caption_text
        self.caption.setText(self.caption_text)
        self.bbox = other.bbox

    def mousePressEvent(self, ev) -> None:
        self.clicked.emit(self)


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------

class DetailView(QWidget):
    def __init__(self, on_back):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.caption = QLabel("")
        self.caption.setStyleSheet("font-size: 16px; padding: 4px;")
        v.addWidget(self.caption)

        self.image_label = QLabel()
        self.image_label.setAlignment(QT_ALIGN_CENTER)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v.addWidget(self.image_label, stretch=1)

        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(on_back)
        v.addWidget(back_btn)

        self._raw_pix: QPixmap | None = None
        self._bbox: tuple[Any, ...] | None = None

    def set_content(self, pix: QPixmap, caption: str, bbox: tuple[Any, ...] | None) -> None:
        self._raw_pix = pix
        self._bbox = bbox
        self.caption.setText(caption)
        self._render()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._render()

    def _render(self) -> None:
        if self._raw_pix is None:
            return
        pix = self._raw_pix.copy()
        if self._bbox and all(v is not None for v in self._bbox):
            x, y, w, h = self._bbox
            painter = QPainter(pix)
            pen = QPen(QColor("#6ee787"))
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawRect(int(x), int(y), int(w), int(h))
            painter.end()
        scaled = pix.scaled(
            self.image_label.size(),
            QT_KEEP_ASPECT_RATIO,
            QT_SMOOTH_TRANSFORMATION,
        )
        self.image_label.setPixmap(scaled)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_ts(ts: str) -> str:
    if not ts:
        return "        "
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M:%S")
    except Exception:
        return ts[-8:]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    cfg = load_config()
    db_path = Path(cfg["storage"]["db_path"])
    storage = Storage(db_path)

    # Purge stale rows on startup
    deleted = storage.purge_old(cfg["storage"].get("retain_days", 30))
    if deleted:
        log.info("Purged %d old observation rows", deleted)

    event_q: queue.Queue[Any] = queue.Queue(maxsize=2000)
    bridge = MqttBridge(cfg, event_q)
    bridge.start()

    app = QApplication(sys.argv)
    app.setApplicationName("Wildlife Watcher")

    win = WildlifeKiosk(cfg, storage, bridge, event_q)
    win.show()

    # Clean shutdown on SIGTERM (systemd stop)
    def _shutdown(*_a):
        log.info("Shutting down")
        bridge.stop()
        storage.close()
        app.quit()
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    return app.exec_()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
