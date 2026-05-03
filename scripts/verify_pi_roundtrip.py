"""Read-only remote diagnostics for the Pi end of the wildlife pipeline.

Despite the historical name, this script does **not** publish anything: it
SSHes into the Pi (using credentials from ``scripts/_pi_creds.load()``) and
runs a sequence of read-only inspection commands — service state, broker
listener, recent MQTT traffic, and the most recent rows in
``observations.db``. No remote state is mutated.

For an actual MQTT-publish → kiosk-ingest → SQLite round-trip check, use
``scripts/verify_e2e_journey.py`` instead.

The deployed Mosquitto broker has ``allow_anonymous false``, so the
``mosquitto_sub`` checks below need credentials. Set ``MQTT_USER`` and
``MQTT_PASS`` in the environment before running. If ``MQTT_PASS`` is
unset, the broker-traffic checks are skipped (with a clear note) so the
non-broker diagnostics still run.
"""

from __future__ import annotations

import logging
import os
import shlex
import sys
from collections.abc import Iterable

from _pi_creds import load as _load_creds
from _ssh_client import build_ssh_client, connect

log = logging.getLogger("verify_pi_roundtrip")

HOST, USER, PASS = _load_creds()
PI_KEY = os.environ.get("PI_KEY") or None
MQTT_USER = os.environ.get("MQTT_USER", "wildlife")
MQTT_PASS = os.environ.get("MQTT_PASS", "")


def _sub(topic: str, count: int, secs: int) -> str:
    if not MQTT_PASS:
        return (
            f"echo '(skipped: MQTT_PASS not set; broker requires auth, "
            f"would have run mosquitto_sub -t {topic})'"
        )
    auth = f"-u {shlex.quote(MQTT_USER)} -P {shlex.quote(MQTT_PASS)}"
    return (
        f"timeout {secs} mosquitto_sub -h 127.0.0.1 {auth} "
        f"-t {shlex.quote(topic)} -C {count} -v 2>&1 "
        f"|| echo '(no messages on {topic} within {secs}s)'"
    )


# Each entry is (label, command, timeout_seconds). Commands are kept read-only.
_DB_LOCATE = (
    "ls /var/lib/wildlife/observations.db 2>/dev/null "
    "|| ls /home/ian/observations.db 2>/dev/null "
    "|| find /home /var -maxdepth 4 -name observations.db 2>/dev/null "
    "| head -n1"
)
_DB_SUMMARY = (
    f"DB=$({_DB_LOCATE}); "
    "if [ -n \"$DB\" ]; then "
    "  sqlite3 \"$DB\" \"SELECT COUNT(*) AS rows, "
    "SUM(CASE WHEN thumb_jpeg IS NOT NULL THEN 1 ELSE 0 END) AS with_thumb, "
    "MAX(ts) AS latest_ts FROM observations;\"; "
    "  echo '--- last 5 ---'; "
    "  sqlite3 -header -column \"$DB\" \"SELECT id, node_id, frame_id, ts, "
    "length(thumb_jpeg) AS jpeg_bytes FROM observations "
    "ORDER BY id DESC LIMIT 5;\"; "
    "else echo 'no observations.db found'; fi"
)
_DB_PATH_LOOKUP = (
    "ls -lh /var/lib/wildlife/observations.db 2>&1 "
    "|| ls -lh /home/ian/observations.db 2>&1 "
    "|| find /home /var -maxdepth 4 -name 'observations.db' 2>/dev/null"
)
CHECKS: list[tuple[str, str, int]] = [
    ("uname", "uname -a && hostname -I", 10),
    (
        "mosquitto-svc",
        "systemctl is-active mosquitto && "
        "systemctl --no-pager -l status mosquitto | head -n 12",
        10,
    ),
    (
        "mosquitto-port",
        "ss -ltn | grep -E ':1883|:8883' || echo 'no listener on 1883/8883'",
        10,
    ),
    (
        "kiosk-svc",
        "systemctl is-active wildlife-kiosk.service 2>/dev/null "
        "|| echo 'kiosk service inactive/missing'",
        10,
    ),
    ("recent-status", _sub("wildlife/status/+", 5, 6), 15),
    ("recent-detect", _sub("wildlife/detections/+", 3, 8), 15),
    (
        "recent-thumbs",
        _sub("wildlife/thumbs/+/+", 1, 8) + " | head -c 300; echo",
        15,
    ),
    ("db-path", _DB_PATH_LOOKUP, 15),
    ("db-summary", _DB_SUMMARY, 20),
]


def run(client, label: str, command: str, timeout: int) -> int:
    truncated = command[:120] + ("..." if len(command) > 120 else "")
    print(f"\n===== [{label}] $ {truncated}")
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=False)
    rc: int = int(stdout.channel.recv_exit_status())
    out = stdout.read().decode("utf-8", errors="replace").rstrip()
    err = stderr.read().decode("utf-8", errors="replace").rstrip()
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    print(f"[rc={rc}]")
    return rc


def main(checks: Iterable[tuple[str, str, int]]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(f"Connecting to {USER}@{HOST} ...")
    client = build_ssh_client()
    try:
        connect(client, HOST, USER, PASS, key_filename=PI_KEY)
    except Exception as exc:
        print(f"SSH connect failed: {exc}")
        return 1
    try:
        for label, cmd, to in checks:
            run(client, label, cmd, to)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(CHECKS))
