"""Stage 4: authenticated live-traffic capture to confirm whether the camera
node is publishing at all, plus connectivity check to 192.168.4.30.
"""

from __future__ import annotations

import os
import shlex
import sys

import paramiko  # type: ignore
from _pi_creds import load as _load_creds

HOST, USER, PASS = _load_creds()
MQTT_USER = os.environ.get("MQTT_USER", "wildlife")
MQTT_PASS = os.environ.get("MQTT_PASS", "")


def run(client, label, cmd, timeout=60):
    print(f"\n===== [{label}]")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    print(stdout.read().decode("utf-8", "replace").rstrip())
    err = stderr.read().decode("utf-8", "replace").rstrip()
    if err:
        print(f"[stderr] {err}")
    print(f"[rc={rc}]")


def main() -> int:
    if not MQTT_PASS:
        sys.stderr.write(
            "error: MQTT_PASS environment variable is required "
            "(broker has allow_anonymous false).\n"
        )
        return 2

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10)
    try:
        run(client, "ping-cam",
            "ping -c 3 -W 2 192.168.4.30", timeout=20)
        sub_cmd = (
            f"timeout 30 mosquitto_sub -h 127.0.0.1 "
            f"-u {shlex.quote(MQTT_USER)} -P {shlex.quote(MQTT_PASS)} "
            f"-t 'wildlife/#' -v 2>&1 || true"
        )
        run(client, "live-30s-all", sub_cmd, timeout=45)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
