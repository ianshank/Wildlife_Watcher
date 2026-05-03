r"""One-shot SFTP deploy of pi-display-node/ to the Pi and run install.sh.

Credentials come from environment variables (no secrets in source):

  PI_HOST       - Pi hostname/IP (default: 192.168.4.21)
  PI_USER       - Pi SSH user    (default: ian)
  PI_PASS       - Pi SSH password (REQUIRED)
  BROKER_USER   - mosquitto broker user the installer will provision
                  (default: wildlife)
  BROKER_PASS   - mosquitto broker password the installer will provision
                  (REQUIRED)

PowerShell example:
    $env:PI_PASS    = '<pi-password>'
    $env:BROKER_PASS = '<broker-password>'
    .\.venv\Scripts\python.exe deploy.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko  # type: ignore

# Local import - keeps the env-var loader in one place across the repo.
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from _pi_creds import load as _load_pi_creds


def _require(env_name: str) -> str:
    val = os.environ.get(env_name, "").strip()
    if not val:
        sys.stderr.write(
            f"error: {env_name} environment variable is required.\n"
        )
        sys.exit(2)
    return val


def main() -> int:
    host, user, pi_pass = _load_pi_creds()
    broker_user = os.environ.get("BROKER_USER", "wildlife").strip() or "wildlife"
    broker_pass = _require("BROKER_PASS")

    local_dir = Path(__file__).parent / "pi-display-node"
    remote_dir = f"/home/{user}/pi-display-node"

    print(f"Connecting to {user}@{host}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host, username=user, password=pi_pass, timeout=10,
                    allow_agent=False, look_for_keys=False)
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
    cmd = (
        f"cd {remote_dir} && chmod +x install.sh && "
        f"export BROKER_USER={broker_user!r} && "
        f"export BROKER_PASS={broker_pass!r} && "
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
