"""Resolve named Pi/camera SSH/network targets without hard-coding LAN IPs.

Resolution precedence (first hit wins):

  1. **YAML targets file** (``PI_TARGETS_FILE`` env, default
     ``~/.wildlife/pi-targets.yaml``). Schema::

         targets:
           camera:
             host: 192.0.2.10
             user: ian
           display:
             host: 192.0.2.20
             user: ian

  2. **Environment variables**:
       * ``camera``  -> ``CAMERA_IP`` / ``CAMERA_USER``
       * ``display`` -> ``PI_HOST`` / ``PI_USER`` (the existing display Pi vars)

  3. **Caller-supplied fallback** (e.g. for first-time bootstrapping when
     no config file exists yet). Pass ``fallback=Target(...)`` only when
     the script truly needs a literal default.

The helper is pure — file I/O is injected via ``file_loader`` so tests
can drive it from in-memory fixtures.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

# YAML is optional; if PyYAML is not installed we silently skip the file
# layer and fall back to env. This keeps the helper usable in minimal
# environments (e.g. firmware-only CI runners).
_yaml: object | None
try:  # pragma: no cover - optional import branch
    import yaml as _yaml_module

    _yaml = _yaml_module
except Exception:  # pragma: no cover - optional import branch
    _yaml = None


_DEFAULT_TARGETS_FILE = "~/.wildlife/pi-targets.yaml"

# Per-target environment variable mapping. Adding a new logical target
# only requires extending this table; resolve_target() does not need to
# change.
_ENV_VARS: dict[str, tuple[str, str]] = {
    # name -> (host_env, user_env)
    "camera": ("CAMERA_IP", "CAMERA_USER"),
    "display": ("PI_HOST", "PI_USER"),
}

_DEFAULT_USER = "ian"


@dataclass(frozen=True)
class Target:
    """Resolved network target for a named Pi/device."""

    host: str
    user: str


FileLoader = Callable[[Path], Mapping[str, object] | None]


def _default_file_loader(path: Path) -> Mapping[str, object] | None:
    """Load and parse a YAML targets file, or return None if absent.

    Returns ``None`` when the file does not exist OR PyYAML is not
    installed; raises only on malformed YAML so misconfiguration is
    caught loudly.
    """
    if not path.exists() or _yaml is None:
        return None
    raw = path.read_text(encoding="utf-8")
    parsed = _yaml.safe_load(raw)  # type: ignore[attr-defined]
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        raise ValueError(
            f"Pi targets file {path} must be a YAML mapping at the top level"
        )
    return parsed


def _from_file(
    name: str,
    *,
    env: Mapping[str, str],
    file_loader: FileLoader,
) -> Target | None:
    # ``env.get(..., default)`` would only fall back when the key is absent;
    # use ``or`` so an empty-string ``PI_TARGETS_FILE`` (e.g. a tester
    # un-setting it via ``$env:PI_TARGETS_FILE = ''``) also drops to the
    # default path instead of crashing on ``Path('')``.
    raw_path = env.get("PI_TARGETS_FILE") or _DEFAULT_TARGETS_FILE
    path = Path(raw_path).expanduser()
    parsed = file_loader(path)
    if parsed is None:
        return None
    targets = parsed.get("targets")
    if not isinstance(targets, dict):
        return None
    entry = targets.get(name)
    if not isinstance(entry, dict):
        return None
    host = entry.get("host")
    if not isinstance(host, str) or not host:
        return None
    user = entry.get("user")
    if not isinstance(user, str) or not user:
        user = _DEFAULT_USER
    return Target(host=host, user=user)


def _from_env(name: str, env: Mapping[str, str]) -> Target | None:
    mapping = _ENV_VARS.get(name)
    if mapping is None:
        return None
    host_var, user_var = mapping
    host = env.get(host_var)
    if not host:
        return None
    user = env.get(user_var) or _DEFAULT_USER
    return Target(host=host, user=user)


def resolve_target(
    name: str,
    *,
    env: Mapping[str, str] | None = None,
    file_loader: FileLoader | None = None,
    fallback: Target | None = None,
) -> Target:
    """Resolve a named Pi target using file -> env -> fallback precedence.

    Args:
        name: Logical target name (e.g. ``"camera"`` or ``"display"``).
        env: Mapping used in place of ``os.environ`` (for tests).
        file_loader: Function that reads a parsed YAML mapping from disk;
            defaults to a real PyYAML loader.
        fallback: Optional last-resort Target if neither file nor env
            resolves. Most callers should leave this ``None`` and surface
            the ``RuntimeError`` so misconfiguration is loud.

    Returns:
        Resolved ``Target``.

    Raises:
        RuntimeError: when no source resolves and no ``fallback`` is given.
    """
    e = os.environ if env is None else env
    fl = _default_file_loader if file_loader is None else file_loader

    from_file = _from_file(name, env=e, file_loader=fl)
    if from_file is not None:
        return from_file

    from_env = _from_env(name, e)
    if from_env is not None:
        return from_env

    if fallback is not None:
        return fallback

    raise RuntimeError(
        f"Cannot resolve Pi target {name!r}: no entry in PI_TARGETS_FILE "
        f"({e.get('PI_TARGETS_FILE', _DEFAULT_TARGETS_FILE)}), no env vars "
        f"({_ENV_VARS.get(name, ('<unknown>', '<unknown>'))[0]}/...), "
        "and no fallback supplied."
    )
