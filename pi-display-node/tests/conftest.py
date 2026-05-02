import sqlite3

import pytest
import yaml


class MockMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload

@pytest.fixture
def test_config(tmp_path):
    cfg = {
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
                "status": "wildlife/status/+"
            }
        },
        "ui": {
            "fullscreen": False,
            "screen_width": 800,
            "screen_height": 480,
            "thumb_grid_cols": 2,
            "thumb_grid_rows": 2,
            "max_feed_rows": 10,
            "min_confidence_to_show": 0.5,
            "refresh_ms": 100,
            "classes_to_highlight": ["bird"]
        }
    }
    cfg_file = tmp_path / "config.yaml"
    with cfg_file.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f)
    return cfg

@pytest.fixture
def mock_db_path(tmp_path):
    db_path = tmp_path / "test.db"

    # Initialize schema
    schema = """
    CREATE TABLE observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        node_id TEXT NOT NULL,
        frame_id TEXT NOT NULL,
        class_name TEXT NOT NULL,
        class_id INTEGER,
        confidence REAL NOT NULL,
        bbox_x INTEGER NOT NULL,
        bbox_y INTEGER NOT NULL,
        bbox_w INTEGER NOT NULL,
        bbox_h INTEGER NOT NULL,
        model TEXT,
        fps REAL,
        thumb_jpeg BLOB,
        confirmed_by TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
    );
    CREATE UNIQUE INDEX idx_obs_node_frame ON observations (node_id, frame_id, class_id);

    CREATE TABLE nodes (
        node_id TEXT PRIMARY KEY,
        last_seen TEXT,
        last_ip TEXT,
        state TEXT,
        notes TEXT
    );
    """
    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema)
    conn.commit()
    conn.close()

    return db_path
