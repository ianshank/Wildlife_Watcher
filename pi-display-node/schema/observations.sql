-- /var/lib/wildlife/observations.db schema

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS observations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,                 -- ISO 8601 UTC
    node_id       TEXT    NOT NULL,
    frame_id      TEXT    NOT NULL,
    class_name    TEXT    NOT NULL,
    class_id      INTEGER,
    confidence    REAL    NOT NULL,
    bbox_x        INTEGER NOT NULL,
    bbox_y        INTEGER NOT NULL,
    bbox_w        INTEGER NOT NULL,
    bbox_h        INTEGER NOT NULL,
    model         TEXT,
    fps           REAL,
    thumb_jpeg    BLOB,                             -- raw JPEG bytes, may be NULL
    confirmed_by  TEXT,                             -- user touch confirmation, future
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_obs_ts          ON observations (ts DESC);
CREATE INDEX IF NOT EXISTS idx_obs_node_ts     ON observations (node_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_obs_class_ts    ON observations (class_name, ts DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_obs_node_frame
    ON observations (node_id, frame_id, class_id);

CREATE TABLE IF NOT EXISTS nodes (
    node_id       TEXT PRIMARY KEY,
    last_seen     TEXT,
    last_ip       TEXT,
    state         TEXT,                             -- 'online' | 'offline'
    notes         TEXT
);
