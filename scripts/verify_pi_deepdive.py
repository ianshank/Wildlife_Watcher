"""Stage 3: read sudo-protected configs and find what's actually running the
Python kiosk (the systemd unit is a one-shot 'readiness check').
"""

from __future__ import annotations

import logging
import shlex
import sys

from _pi_creds import load as _load_creds
from _ssh_client import build_ssh_client, connect

log = logging.getLogger("verify_pi_deepdive")

HOST, USER, PASS = _load_creds()


def shell(client, label, cmd, timeout=20):
    print(f"\n===== [{label}]")
    chan = client.get_transport().open_session()
    chan.get_pty()
    chan.settimeout(timeout)
    chan.exec_command(f"sudo -S -p '' bash -c {shlex.quote(cmd)}")
    chan.send(PASS + "\n")
    out_chunks = []
    while True:
        if chan.recv_ready():
            out_chunks.append(chan.recv(65536).decode("utf-8", "replace"))
        if chan.exit_status_ready() and not chan.recv_ready():
            break
    rc = chan.recv_exit_status()
    while chan.recv_ready():
        out_chunks.append(chan.recv(65536).decode("utf-8", "replace"))
    print("".join(out_chunks).rstrip())
    print(f"[rc={rc}]")


def plain(client, label, cmd, timeout=20):
    print(f"\n===== [{label}]")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace").rstrip()
    err = stderr.read().decode("utf-8", "replace").rstrip()
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    print(f"[rc={rc}]")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    client = build_ssh_client()
    try:
        connect(client, HOST, USER, PASS)
    except Exception as exc:
        print(f"FAILED: SSH connect failed: {exc}")
        client.close()
        return 1
    try:
        shell(client, "etc-config", "cat /etc/wildlife/config.yaml")
        shell(client, "wildlife-conf",
              "cat /etc/mosquitto/conf.d/wildlife.conf")
        shell(client, "passwd-users",
              "ls -l /etc/mosquitto/passwd 2>/dev/null && "
              "cut -d: -f1 /etc/mosquitto/passwd 2>/dev/null")
        shell(client, "mosquitto-tail",
              "tail -n 80 /var/log/mosquitto/mosquitto.log")
        shell(client, "kiosk-unit",
              "cat /etc/systemd/system/wildlife-kiosk.service 2>/dev/null "
              "|| systemctl cat wildlife-kiosk.service")
        plain(client, "py-procs",
              "ps -ef | grep -E 'python|wildlife|kiosk' | grep -v grep")
        plain(client, "autostart",
              "ls -la /home/ian/.config/autostart/ 2>/dev/null; "
              "ls -la /etc/xdg/autostart/ 2>/dev/null | grep -i wildlife")
        plain(client, "user-services",
              "systemctl --user list-units --type=service --no-pager 2>&1 "
              "| head -n 30")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
