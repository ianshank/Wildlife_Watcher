r"""One-shot SFTP deploy of pi-display-node/ to the Pi and run install.sh.

Credentials come from environment variables (no secrets in source):

  PI_HOST       - Pi hostname/IP (default: 192.168.4.21)
  PI_USER       - Pi SSH user    (default: ian)
  PI_PASS       - Pi SSH password (REQUIRED)
  BROKER_USER   - mosquitto broker user the installer will provision
                  (default: wildlife)
  BROKER_PASS   - mosquitto broker password the installer will provision
                  (REQUIRED)

  PI_HOST_KEY_POLICY  - one of {strict,auto} (default: strict).
                        ``strict`` uses paramiko.RejectPolicy and requires
                        the Pi's host key to already be in the user's
                        ``~/.ssh/known_hosts``; ``auto`` falls back to
                        AutoAddPolicy and prints a MITM warning.
  PI_KNOWN_HOSTS      - path to a known_hosts file to load (default:
                        ``~/.ssh/known_hosts``).

PowerShell example:
    $env:PI_PASS    = '<pi-password>'
    $env:BROKER_PASS = '<broker-password>'
    .\.venv\Scripts\python.exe deploy.py
"""
from __future__ import annotations

import contextlib
import os
import shlex
import sys
from pathlib import Path

import paramiko

# Local import - keeps the env-var loader and SSH wiring in one place
# across the repo. ``_ssh_client.connect`` centralises the auth-priority
# matrix (key + password vs. password-only) so ``deploy.py`` does not
# need to re-implement (and unit-test) the same logic.
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from _pi_creds import load as _load_pi_creds
from _ssh_client import connect as _ssh_connect


def _require(env_name: str) -> str:
    val = os.environ.get(env_name, "").strip()
    if not val:
        sys.stderr.write(
            f"error: {env_name} environment variable is required.\n"
        )
        sys.exit(2)
    return val


def _build_ssh_client() -> paramiko.SSHClient:
    """Build an ``SSHClient`` with a safe-by-default host-key policy.

    Defaults to ``RejectPolicy`` after loading the user's known_hosts,
    which mitigates MITM. Set ``PI_HOST_KEY_POLICY=auto`` to opt back
    into ``AutoAddPolicy`` (e.g. on first contact in a trusted LAN).
    """
    client = paramiko.SSHClient()
    known_hosts = os.environ.get(
        "PI_KNOWN_HOSTS", str(Path.home() / ".ssh" / "known_hosts")
    )
    with contextlib.suppress(Exception):
        client.load_system_host_keys()
    if known_hosts and Path(known_hosts).expanduser().exists():
        try:
            client.load_host_keys(str(Path(known_hosts).expanduser()))
        except Exception as exc:
            sys.stderr.write(
                f"warning: failed to load known_hosts {known_hosts}: {exc}\n"
            )

    policy = os.environ.get("PI_HOST_KEY_POLICY", "strict").strip().lower()
    if policy == "auto":
        sys.stderr.write(
            "warning: PI_HOST_KEY_POLICY=auto \u2014 trusting unknown host keys "
            "(MITM risk). Switch to 'strict' once the Pi key is in "
            "known_hosts.\n"
        )
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    return client


def main() -> int:
    host, user, pi_pass = _load_pi_creds()
    broker_user = os.environ.get("BROKER_USER", "wildlife").strip() or "wildlife"
    broker_pass = _require("BROKER_PASS")
    # Optional public-key auth: PI_KEY wins over PI_PASS when set, but the
    # password is still threaded through so paramiko can decrypt encrypted
    # private keys.
    pi_key = os.environ.get("PI_KEY") or None

    # ``deploy.py`` shells the installer with ``sudo -S`` and pipes the Pi
    # password into stdin; key-only auth is therefore not sufficient on its
    # own. Surface a clear error rather than letting sudo hang forever on a
    # blank stdin if the operator forgot ``PI_PASS``.
    if not pi_pass:
        sys.stderr.write(
            "error: PI_PASS is required for deploy.py because the installer "
            "runs `sudo -S` on the Pi. Set PI_PASS even when PI_KEY is "
            "configured for SSH auth.\n"
        )
        return 2

    local_dir = Path(__file__).parent / "pi-display-node"
    remote_dir = f"/home/{user}/pi-display-node"

    print(f"Connecting to {user}@{host}...")
    ssh = _build_ssh_client()
    try:
        # Delegate the auth-priority matrix (key + optional password vs.
        # password-only) to the centralised, unit-tested helper.
        _ssh_connect(
            ssh,
            host,
            user,
            password=pi_pass,
            key_filename=pi_key,
            timeout=10,
        )
    except Exception as e:
        print(f"SSH failed: {e}")
        return 1

    print("Connected. Copying files via SFTP...")
    sftp = ssh.open_sftp()
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)

    def put_dir(local_path: Path, remote_path: str) -> None:
        for item in local_path.iterdir():
            rp = f"{remote_path}/{item.name}"
            if item.is_dir():
                try:
                    sftp.stat(rp)
                except FileNotFoundError:
                    sftp.mkdir(rp)
                put_dir(item, rp)
            else:
                sftp.put(str(item), rp)

    put_dir(local_dir, remote_dir)
    print("Files copied.")
    sftp.close()

    print("Running installer...")
    # The installer skips its interactive prompt when BROKER_PASS is set.
    # shlex.quote is critical here: repr() / !r is not a valid shell quote
    # (it would let bash $-expand or backtick-execute values containing
    # single quotes mixed with metacharacters).
    cmd = (
        f"cd {shlex.quote(remote_dir)} && chmod +x install.sh && "
        f"export BROKER_USER={shlex.quote(broker_user)} && "
        f"export BROKER_PASS={shlex.quote(broker_pass)} && "
        f"sudo -S -E bash install.sh"
    )
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    stdin.write(pi_pass + "\n")
    stdin.flush()
    for line in iter(stdout.readline, ""):
        print(line.encode(sys.stdout.encoding, errors="replace")
              .decode(sys.stdout.encoding), end="")

    exit_status = stdout.channel.recv_exit_status()
    print(f"Installer finished with status {exit_status}")
    if exit_status != 0:
        print("Stderr:")
        print(stderr.read().decode(errors="replace"))

    ssh.close()
    return exit_status


if __name__ == "__main__":
    raise SystemExit(main())
