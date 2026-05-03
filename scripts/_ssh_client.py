"""Reusable paramiko SSH client factory with safe-by-default host-key handling.

Provides the SSH-policy logic used by the ``scripts/verify_pi_*.py``
family. Defaults to ``paramiko.RejectPolicy`` after loading the user's
``known_hosts`` so we do not silently accept unknown host keys (MITM
mitigation). Set ``PI_HOST_KEY_POLICY=auto`` to fall back to
``AutoAddPolicy`` (with a WARNING) for first-contact bootstrapping.

Environment variables
---------------------
PI_HOST_KEY_POLICY
    ``strict`` (default) -> ``RejectPolicy``;
    ``auto`` -> ``AutoAddPolicy`` (logs WARNING).
PI_KNOWN_HOSTS
    Path to a known_hosts file; defaults to ``~/.ssh/known_hosts``.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import paramiko

log = logging.getLogger(__name__)


def build_ssh_client() -> paramiko.SSHClient:
    """Build an ``SSHClient`` with a safe-by-default missing-key policy.

    Returns a fresh client; callers still own ``connect()``/``close()``.
    """
    client = paramiko.SSHClient()

    # Load any existing known_hosts so RejectPolicy will accept the Pi
    # once it has been added there.
    try:
        client.load_system_host_keys()
    except Exception as exc:  # pragma: no cover - environmental
        log.debug("load_system_host_keys failed: %s", exc)

    known_hosts = os.environ.get(
        "PI_KNOWN_HOSTS", str(Path.home() / ".ssh" / "known_hosts")
    )
    if known_hosts:
        kh_path = Path(known_hosts).expanduser()
        if kh_path.exists():
            try:
                client.load_host_keys(str(kh_path))
            except Exception as exc:
                log.warning("Failed to load known_hosts %s: %s", kh_path, exc)

    policy = os.environ.get("PI_HOST_KEY_POLICY", "strict").strip().lower()
    if policy == "auto":
        log.warning(
            "PI_HOST_KEY_POLICY=auto - trusting unknown host keys (MITM "
            "risk). Switch to 'strict' once the Pi key is in known_hosts."
        )
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    return client


def connect(
    client: paramiko.SSHClient,
    host: str,
    user: str,
    password: str,
    *,
    timeout: int = 10,
    banner_timeout: int = 10,
    auth_timeout: int = 10,
) -> None:
    """Convenience wrapper around ``SSHClient.connect`` with sane defaults.

    Always disables agent + key lookup so password-only credentials
    (which is how the Pi is provisioned today) work predictably across
    environments.
    """
    client.connect(
        host,
        username=user,
        password=password,
        timeout=timeout,
        banner_timeout=banner_timeout,
        auth_timeout=auth_timeout,
        allow_agent=False,
        look_for_keys=False,
    )
