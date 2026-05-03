"""Stage 2 of remote verification: pull broker creds from the kiosk config,
re-subscribe authenticated, and inspect mosquitto + kiosk service logs to
explain why observations.db is empty.
"""

from __future__ import annotations

import sys

import paramiko  # type: ignore
from _pi_creds import load as _load_creds

HOST, USER, PASS = _load_creds()

CHECKS: list[tuple[str, str, int]] = [
    ("kiosk-config-path", "ls /etc/wildlife-kiosk/config.yaml /home/ian/pi-display-node/kiosk/config.yaml /opt/wildlife/config.yaml 2>/dev/null; "
                          "find /etc /home /opt -maxdepth 5 -name 'config.yaml' -path '*wildlife*' 2>/dev/null", 15),
    ("kiosk-config",      "for p in /etc/wildlife-kiosk/config.yaml /home/ian/pi-display-node/kiosk/config.yaml /opt/wildlife/config.yaml; "
                          "do [ -f \"$p\" ] && echo \"=== $p ===\" && sudo -n cat \"$p\" 2>/dev/null || cat \"$p\" 2>/dev/null; done", 15),
    ("mosquitto-conf",    "ls /etc/mosquitto/conf.d/ 2>/dev/null; sudo -n cat /etc/mosquitto/mosquitto.conf 2>/dev/null | grep -v '^#' | grep -v '^$' | head -n 30", 15),
    ("mosquitto-passwd",  "ls -l /etc/mosquitto/passwd 2>/dev/null; sudo -n cat /etc/mosquitto/passwd 2>/dev/null | cut -d: -f1", 10),
    ("mosquitto-log",     "sudo -n tail -n 60 /var/log/mosquitto/mosquitto.log 2>/dev/null || tail -n 60 /var/log/mosquitto/mosquitto.log 2>&1", 15),
    ("kiosk-journal",     "journalctl -u wildlife-kiosk.service -n 40 --no-pager 2>&1 | tail -n 40", 20),
    ("camera-seen",       "sudo -n grep -E 'New (client|connection)' /var/log/mosquitto/mosquitto.log 2>/dev/null | tail -n 20 || echo '(need sudo)'", 15),
    ("ip-arp",            "ip neigh | grep -E '^192\\.168\\.' | sort", 10),
]


def run(client: paramiko.SSHClient, label: str, command: str, timeout: int) -> int:
    print(f"\n===== [{label}]")
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


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10, banner_timeout=10, auth_timeout=10)
    try:
        for label, cmd, to in CHECKS:
            run(client, label, cmd, to)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
