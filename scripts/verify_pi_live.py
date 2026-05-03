"""Stage 4: authenticated live-traffic capture to confirm whether the camera
node is publishing at all, plus a connectivity check to ``CAMERA_IP``.

Environment variables
---------------------
MQTT_USER, MQTT_PASS
    Credentials for the Pi-side ``mosquitto_sub`` (broker has
    ``allow_anonymous false``). ``MQTT_PASS`` is required.
CAMERA_IP
    LAN address of the camera node to ``ping``. Resolved via
    :mod:`_pi_targets` (``PI_TARGETS_FILE`` -> ``CAMERA_IP`` env). No
    literal fallback — set one of those sources before running.
CAMERA_PING_COUNT, CAMERA_PING_TIMEOUT_S
    Tunables for the ping command (defaults: 3 packets, 2 s timeout).
LIVE_CAPTURE_DURATION_S
    How long ``mosquitto_sub`` runs (default: 30 s).
See also ``scripts/_ssh_client.py`` for ``PI_HOST_KEY_POLICY`` /
``PI_KNOWN_HOSTS`` MITM-mitigation knobs.
"""

from __future__ import annotations

import logging
import os
import shlex
import sys

from _pi_creds import load as _load_creds
from _pi_targets import resolve_target
from _ssh_client import build_ssh_client, connect

log = logging.getLogger("verify_pi_live")

HOST, USER, PASS = _load_creds()
MQTT_USER = os.environ.get("MQTT_USER", "wildlife")
MQTT_PASS = os.environ.get("MQTT_PASS", "")
# Camera target: PI_TARGETS_FILE -> CAMERA_IP env. No literal fallback;
# misconfiguration surfaces as a RuntimeError at import time.
CAMERA_IP = resolve_target("camera").host
CAMERA_PING_COUNT = int(os.environ.get("CAMERA_PING_COUNT", "3"))
CAMERA_PING_TIMEOUT_S = int(os.environ.get("CAMERA_PING_TIMEOUT_S", "2"))
LIVE_CAPTURE_DURATION_S = int(os.environ.get("LIVE_CAPTURE_DURATION_S", "30"))


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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not MQTT_PASS:
        sys.stderr.write(
            "error: MQTT_PASS environment variable is required "
            "(broker has allow_anonymous false).\n"
        )
        return 2

    client = build_ssh_client()
    try:
        connect(client, HOST, USER, PASS)
    except Exception as exc:
        print(f"FAILED: SSH connect failed: {exc}")
        client.close()
        return 1
    try:
        ping_cmd = (
            f"ping -c {CAMERA_PING_COUNT} -W {CAMERA_PING_TIMEOUT_S} "
            f"{shlex.quote(CAMERA_IP)}"
        )
        run(client, "ping-cam", ping_cmd,
            timeout=CAMERA_PING_COUNT * (CAMERA_PING_TIMEOUT_S + 5))
        sub_cmd = (
            f"timeout {LIVE_CAPTURE_DURATION_S} mosquitto_sub -h 127.0.0.1 "
            f"-u {shlex.quote(MQTT_USER)} -P {shlex.quote(MQTT_PASS)} "
            f"-t 'wildlife/#' -v 2>&1 || true"
        )
        run(client, f"live-{LIVE_CAPTURE_DURATION_S}s-all", sub_cmd,
            timeout=LIVE_CAPTURE_DURATION_S + 15)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
