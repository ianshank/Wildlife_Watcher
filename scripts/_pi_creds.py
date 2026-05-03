"""Shared Pi SSH credential loader for verify_pi_*.py scripts.

Reads from environment variables — never hard-codes secrets in the repo:
  PI_HOST  (resolved via :mod:`_pi_targets`; required unless a
           ``PI_TARGETS_FILE`` entry exists for the ``display`` target)
  PI_USER  (resolved via :mod:`_pi_targets`; defaults to ``ian`` only when
           no other source is configured)
  PI_PASS  (optional if PI_KEY is set; otherwise required)
  PI_KEY   (optional path to a private key for public-key auth)

Set them in your shell before running, e.g. in PowerShell:
    $env:PI_PASS = "<your-pi-password>"
    $env:PI_KEY  = "$HOME/.ssh/id_ed25519"
or in bash:
    export PI_PASS="<your-pi-password>"
    export PI_KEY="$HOME/.ssh/id_ed25519"

Credentials.load_from_env() is the new entry point; the legacy
``load()`` 3-tuple is kept for backwards compatibility with existing
``verify_pi_*.py`` scripts.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass

from _pi_targets import resolve_target


@dataclass(frozen=True)
class Credentials:
    """Resolved Pi SSH credentials (immutable)."""

    host: str
    user: str
    password: str | None
    key_path: str | None

    def as_legacy_tuple(self) -> tuple[str, str, str]:
        """Return ``(host, user, password)``; password must be set.

        Used by callers that have not been migrated to the dataclass
        API yet. Raises if ``password`` is None.
        """
        if self.password is None:
            raise RuntimeError(
                "Credentials.as_legacy_tuple requires a password; set PI_PASS "
                "or migrate the caller to use the Credentials dataclass."
            )
        return self.host, self.user, self.password

    @classmethod
    def load_from_env(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> Credentials:
        """Load credentials from a mapping (defaults to ``os.environ``).

        Resolution rules:
          * ``host`` / ``user`` resolved by ``_pi_targets.resolve_target('display')``
            using the targets file -> env precedence (no literal fallback).
          * ``key_path`` from ``PI_KEY`` (None if unset/empty).
          * ``password`` from ``PI_PASS`` (None if unset/empty).
          * At least one of ``password`` or ``key_path`` must be set;
            ``RuntimeError`` is raised otherwise.
        """
        e = os.environ if env is None else env
        target = resolve_target("display", env=e)
        key_path = e.get("PI_KEY") or None
        password = e.get("PI_PASS") or None
        if password is None and key_path is None:
            raise RuntimeError(
                "Either PI_PASS or PI_KEY must be set for Pi SSH access."
            )
        return cls(
            host=target.host,
            user=target.user,
            password=password,
            key_path=key_path,
        )


def load() -> tuple[str, str, str]:
    """Legacy 3-tuple loader. Exits the process on misconfiguration.

    Behaviour:
      * Resolves ``host`` / ``user`` via :func:`_pi_targets.resolve_target`.
        A ``RuntimeError`` (no YAML entry, no env vars) is caught and
        translated into a friendly error + ``sys.exit(2)`` so callers
        see a configuration hint instead of a Python stack trace.
      * Requires ``PI_PASS``. Key-only auth is intentionally *not*
        supported by this 3-tuple shim because callers cannot forward
        a key path to :func:`_ssh_client.connect`. New scripts should
        use :func:`load_or_exit` (which returns a :class:`Credentials`
        dataclass carrying both ``password`` and ``key_path``).
    """
    try:
        target = resolve_target("display")
    except RuntimeError as exc:
        sys.stderr.write(
            f"error: cannot resolve display Pi target: {exc}\n"
            "  Hint: set PI_HOST/PI_USER, or create ~/.wildlife/pi-targets.yaml\n"
            "        with a 'display' entry. See README.md.\n"
        )
        sys.exit(2)
    pw = os.environ.get("PI_PASS")
    if not pw:
        sys.stderr.write(
            "error: PI_PASS environment variable is required.\n"
            "  PowerShell:  $env:PI_PASS = '<password>'\n"
            "  bash:        export PI_PASS='<password>'\n"
            "  Note: PI_KEY-only auth requires load_or_exit() (returns a\n"
            "  Credentials dataclass), not this legacy 3-tuple loader.\n"
        )
        sys.exit(2)
    return target.host, target.user, pw


def load_or_exit(env: Mapping[str, str] | None = None) -> Credentials:
    """Key-aware credential loader for verify_pi_*.py scripts.

    Wraps :meth:`Credentials.load_from_env` so misconfiguration produces
    a friendly ``sys.exit(2)`` (with a configuration hint) instead of a
    Python stack trace.

    Unlike :func:`load`, this returns the full :class:`Credentials`
    dataclass — including ``key_path`` — so callers can forward
    ``key_filename=creds.key_path`` to :func:`_ssh_client.connect` and
    support PI_KEY-only auth (no PI_PASS required when PI_KEY is set).
    """
    try:
        return Credentials.load_from_env(env=env)
    except RuntimeError as exc:
        sys.stderr.write(
            f"error: cannot load Pi SSH credentials: {exc}\n"
            "  Hint: set PI_HOST/PI_USER (or pi-targets.yaml display entry),\n"
            "        and at least one of PI_PASS or PI_KEY. See README.md.\n"
        )
        sys.exit(2)
