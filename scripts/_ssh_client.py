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
    password: str | None = None,
    *,
    key_filename: str | None = None,
    timeout: int = 10,
    banner_timeout: int = 10,
    auth_timeout: int = 10,
) -> None:
    """Convenience wrapper around ``SSHClient.connect`` with sane defaults.

    Authentication priority:
      1. ``key_filename`` (recommended) — public-key auth; agent + on-disk
         key lookup are enabled so paramiko can decrypt the key from the
         user's normal places.
      2. ``password`` — bootstrap fallback for nodes provisioned without a
         key. Agent + key lookup are disabled so password-only credentials
         work predictably across environments (matches legacy behaviour).

    Either ``password`` or ``key_filename`` must be provided.
    """
    if key_filename is None and password is None:
        raise ValueError(
            "connect() requires either key_filename= or password=; both are None"
        )

    if key_filename is not None:
        client.connect(
            host,
            username=user,
            key_filename=key_filename,
            password=password,
            timeout=timeout,
            banner_timeout=banner_timeout,
            auth_timeout=auth_timeout,
            allow_agent=True,
            look_for_keys=True,
        )
        return

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
