import sqlite3
from datetime import datetime, timezone

from wildlife_kiosk import DetectionEvent, Storage


def test_insert_detection(mock_db_path):
    storage = Storage(mock_db_path)
    ev = DetectionEvent(
        ts="2026-05-01T12:00:00Z",
        node_id="node1",
        frame_id="frame1",
        class_name="bird",
        class_id=1,
        confidence=0.9,
        bbox=(10, 10, 100, 100),
        model="yolo",
        fps=10.0
    )
    obs_id = storage.insert_detection(ev, b"dummy_jpeg")
    assert obs_id > 0

    # Verify via DB
    conn = sqlite3.connect(str(mock_db_path))
    row = conn.execute("SELECT * FROM observations WHERE id = ?", (obs_id,)).fetchone()
    assert row is not None
    assert row[1] == "2026-05-01T12:00:00Z"
    assert row[2] == "node1"
    assert row[3] == "frame1"
    assert row[13] == b"dummy_jpeg"
    conn.close()

def test_update_thumb(mock_db_path):
    storage = Storage(mock_db_path)
    ev = DetectionEvent(
        ts="2026-05-01T12:00:00Z",
        node_id="node1",
        frame_id="frame1",
        class_name="bird",
        class_id=1,
        confidence=0.9,
        bbox=(10, 10, 100, 100),
        model="yolo",
        fps=10.0
    )
    obs_id = storage.insert_detection(ev, None)
    assert storage.thumb_for(obs_id) is None

    storage.update_thumb("node1", "frame1", b"new_jpeg")
    assert storage.thumb_for(obs_id) == b"new_jpeg"


def test_update_thumb_missing_row_is_noop(mock_db_path):
    storage = Storage(mock_db_path)

    storage.update_thumb("missing-node", "missing-frame", b"new_jpeg")

    conn = sqlite3.connect(str(mock_db_path))
    count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    conn.close()
    assert count == 0

def test_upsert_node(mock_db_path):
    storage = Storage(mock_db_path)
    storage.upsert_node("node1", "online", "192.168.1.100", "2026-05-01T12:00:00Z")

    conn = sqlite3.connect(str(mock_db_path))
    row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", ("node1",)).fetchone()
    assert row[1] == "2026-05-01T12:00:00Z"
    assert row[2] == "192.168.1.100"
    assert row[3] == "online"

    # Update
    storage.upsert_node("node1", "offline", None, "2026-05-01T12:01:00Z")
    row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", ("node1",)).fetchone()
    assert row[1] == "2026-05-01T12:01:00Z"
    assert row[2] == "192.168.1.100"  # IP should be coalesced
    assert row[3] == "offline"
    conn.close()

def test_recent_observations(mock_db_path):
    storage = Storage(mock_db_path)
    for i in range(5):
        ev = DetectionEvent(
            ts=f"2026-05-01T12:00:0{i}Z",
            node_id="node1",
            frame_id=f"frame{i}",
            class_name="bird",
            class_id=1,
            confidence=0.9,
            bbox=(10, 10, 100, 100),
            model="yolo",
            fps=10.0
        )
        storage.insert_detection(ev, None)

    recent = storage.recent_observations(3)
    assert len(recent) == 3
    # Check if they are descending by ts
    assert recent[0]["ts"] == "2026-05-01T12:00:04Z"
    assert recent[1]["ts"] == "2026-05-01T12:00:03Z"
    assert recent[2]["ts"] == "2026-05-01T12:00:02Z"


def test_purge_old_returns_deleted_row_count(mock_db_path):
    storage = Storage(mock_db_path)
    old_event = DetectionEvent(
        ts="2000-01-01T00:00:00Z",
        node_id="node1",
        frame_id="old-frame",
        class_name="bird",
        class_id=1,
        confidence=0.9,
        bbox=(10, 10, 100, 100),
        model="yolo",
        fps=10.0,
    )
    recent_event = DetectionEvent(
        ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        node_id="node1",
        frame_id="recent-frame",
        class_name="bird",
        class_id=1,
        confidence=0.9,
        bbox=(10, 10, 100, 100),
        model="yolo",
        fps=10.0,
    )
    storage.insert_detection(old_event, None)
    storage.insert_detection(recent_event, None)

    deleted = storage.purge_old(30)

    assert deleted == 1
    recent = storage.recent_observations(10)
    assert len(recent) == 1
    assert recent[0]["frame_id"] == "recent-frame"
