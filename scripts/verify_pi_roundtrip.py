"""One-shot remote verification of the Pi end of the wildlife pipeline.

Connects via paramiko (same creds as deploy.py) and runs a sequence of
read-only diagnostic commands. No remote state is mutated.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable

import paramiko  # type: ignore
from _pi_creds import load as _load_creds

HOST, USER, PASS = _load_creds()

# Each entry is (label, command, timeout_seconds). Commands are kept read-only.
CHECKS: list[tuple[str, str, int]] = [
    ("uname",          "uname -a && hostname -I", 10),
    ("mosquitto-svc",  "systemctl is-active mosquitto && systemctl --no-pager -l status mosquitto | head -n 12", 10),
    ("mosquitto-port", "ss -ltn | grep -E ':1883|:8883' || echo 'no listener on 1883/8883'", 10),
    ("kiosk-svc",      "systemctl is-active wildlife-kiosk.service 2>/dev/null || echo 'kiosk service inactive/missing'", 10),
    ("recent-status",  "timeout 6 mosquitto_sub -h 127.0.0.1 -t 'wildlife/status/+' -C 5 -v 2>&1 || echo '(no status messages within 6s)'", 15),
    ("recent-detect",  "timeout 8 mosquitto_sub -h 127.0.0.1 -t 'wildlife/detections/+' -C 3 -v 2>&1 || echo '(no detections within 8s)'", 15),
    ("recent-thumbs",  "timeout 8 mosquitto_sub -h 127.0.0.1 -t 'wildlife/thumbs/+/+' -C 1 -v 2>&1 | head -c 300; echo", 15),
    ("db-path",        "ls -lh /var/lib/wildlife/observations.db 2>&1 || ls -lh /home/ian/observations.db 2>&1 || find /home /var -maxdepth 4 -name 'observations.db' 2>/dev/null", 15),
    ("db-summary",     "DB=$(ls /var/lib/wildlife/observations.db 2>/dev/null || ls /home/ian/observations.db 2>/dev/null || find /home /var -maxdepth 4 -name observations.db 2>/dev/null | head -n1); "
                       "if [ -n \"$DB\" ]; then sqlite3 \"$DB\" \"SELECT COUNT(*) AS rows, "
                       "SUM(CASE WHEN thumb_jpeg IS NOT NULL THEN 1 ELSE 0 END) AS with_thumb, "
                       "MAX(ts) AS latest_ts FROM observations;\"; "
                       "echo '--- last 5 ---'; "
                       "sqlite3 -header -column \"$DB\" \"SELECT id, node_id, frame_id, ts, length(thumb_jpeg) AS jpeg_bytes FROM observations ORDER BY id DESC LIMIT 5;\"; "
                       "else echo 'no observations.db found'; fi", 20),
]


def run(client: paramiko.SSHClient, label: str, command: str, timeout: int) -> int:
    print(f"\n===== [{label}] $ {command[:120]}{'...' if len(command) > 120 else ''}")
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=False)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").rstrip()
    err = stderr.read().decode("utf-8", errors="replace").rstrip()
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    print(f"[rc={rc}]")
    return rc


def main(checks: Iterable[tuple[str, str, int]]) -> int:
    print(f"Connecting to {USER}@{HOST} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, username=USER, password=PASS, timeout=10, banner_timeout=10, auth_timeout=10)
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
