from __future__ import annotations

import sqlite3

from wildlife_kiosk import DetectionEvent, Storage


def _table_columns(conn: sqlite3.Connection, table_name: str) -> list[tuple[str, str]]:
    return [
        (str(row[1]), str(row[2]).upper())
        for row in conn.execute(f"PRAGMA table_info({table_name})")
    ]


def _index_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA index_list({table_name})")}


def test_storage_schema_matches_checked_in_sql(mock_db_path) -> None:
    storage = Storage(mock_db_path)
    detection = DetectionEvent(
        ts="2026-05-03T12:00:00Z",
        node_id="node-1",
        frame_id="frame-001",
        class_name="bird",
        class_id=0,
        confidence=0.98,
        bbox=(10, 20, 30, 40),
        model="ethos-u55",
        fps=12.5,
    )

    obs_id = storage.insert_detection(detection, None)
    storage.update_thumb("node-1", "frame-001", b"jpeg-bytes")
    storage.upsert_node("node-1", "online", "192.168.1.12", detection.ts)
    storage.close()

    assert obs_id > 0

    conn = sqlite3.connect(str(mock_db_path))
    assert _table_columns(conn, "observations") == [
        ("id", "INTEGER"),
        ("ts", "TEXT"),
        ("node_id", "TEXT"),
        ("frame_id", "TEXT"),
        ("class_name", "TEXT"),
        ("class_id", "INTEGER"),
        ("confidence", "REAL"),
        ("bbox_x", "INTEGER"),
        ("bbox_y", "INTEGER"),
        ("bbox_w", "INTEGER"),
        ("bbox_h", "INTEGER"),
        ("model", "TEXT"),
        ("fps", "REAL"),
        ("thumb_jpeg", "BLOB"),
        ("confirmed_by", "TEXT"),
        ("created_at", "TEXT"),
    ]
    assert _table_columns(conn, "nodes") == [
        ("node_id", "TEXT"),
        ("last_seen", "TEXT"),
        ("last_ip", "TEXT"),
        ("state", "TEXT"),
        ("notes", "TEXT"),
    ]
    assert _index_names(conn, "observations") >= {
        "idx_obs_ts",
        "idx_obs_node_ts",
        "idx_obs_class_ts",
        "idx_obs_node_frame",
    }

    observation = conn.execute(
        "SELECT class_name, thumb_jpeg FROM observations WHERE id = ?",
        (obs_id,),
    ).fetchone()
    node = conn.execute(
        "SELECT state, last_ip FROM nodes WHERE node_id = ?",
        ("node-1",),
    ).fetchone()
    conn.close()

    assert observation == ("bird", b"jpeg-bytes")
    assert node == ("online", "192.168.1.12")
