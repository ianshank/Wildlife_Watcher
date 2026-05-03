"""Unit tests for the pi-target resolver.

Drives ``_pi_targets.resolve_target`` from in-memory env mappings and an
injected file_loader, so the tests do not touch the real filesystem.
"""
from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _pi_targets  # noqa: E402
from _pi_targets import Target, resolve_target  # noqa: E402


def _loader(payload: Mapping[str, object] | None):
    """Return a file_loader that always yields the given payload."""

    def _load(_path: Path) -> Mapping[str, object] | None:
        return payload

    return _load


def test_resolve_target_prefers_yaml_file_over_env():
    payload = {
        "targets": {
            "camera": {"host": "10.0.0.5", "user": "pi"},
        }
    }
    env = {"CAMERA_IP": "192.0.2.10", "CAMERA_USER": "ian"}
    target = resolve_target(
        "camera", env=env, file_loader=_loader(payload)
    )
    assert target == Target(host="10.0.0.5", user="pi")


def test_resolve_target_falls_back_to_env_when_file_missing():
    env = {"CAMERA_IP": "192.0.2.10", "CAMERA_USER": "ian"}
    target = resolve_target(
        "camera", env=env, file_loader=_loader(None)
    )
    assert target == Target(host="192.0.2.10", user="ian")


def test_resolve_target_uses_default_user_when_user_env_missing():
    env = {"CAMERA_IP": "192.0.2.10"}
    target = resolve_target(
        "camera", env=env, file_loader=_loader(None)
    )
    assert target == Target(host="192.0.2.10", user="ian")


def test_resolve_target_uses_fallback_when_nothing_resolves():
    env: dict[str, str] = {}
    fb = Target(host="192.0.2.99", user="ian")
    target = resolve_target(
        "camera", env=env, file_loader=_loader(None), fallback=fb
    )
    assert target is fb


def test_resolve_target_raises_when_no_source_and_no_fallback():
    env: dict[str, str] = {}
    with pytest.raises(RuntimeError, match="Cannot resolve Pi target"):
        resolve_target("camera", env=env, file_loader=_loader(None))


def test_resolve_target_yaml_entry_with_missing_host_falls_through_to_env():
    """A malformed YAML entry must not silently mask the env source."""
    payload = {"targets": {"camera": {"user": "pi"}}}  # no host
    env = {"CAMERA_IP": "192.0.2.10"}
    target = resolve_target(
        "camera", env=env, file_loader=_loader(payload)
    )
    assert target == Target(host="192.0.2.10", user="ian")


def test_resolve_target_unknown_name_raises():
    """Names not in the env-var map and not in the file must raise."""
    env: dict[str, str] = {}
    with pytest.raises(RuntimeError, match="Cannot resolve Pi target 'mystery'"):
        resolve_target("mystery", env=env, file_loader=_loader(None))


def test_default_file_loader_returns_none_when_path_missing(tmp_path):
    """Built-in loader must gracefully return None for absent files."""
    missing = tmp_path / "does-not-exist.yaml"
    assert _pi_targets._default_file_loader(missing) is None


def test_default_file_loader_parses_real_yaml_file(tmp_path):
    """Smoke-test the real PyYAML path end-to-end (covers safe_load branch)."""
    pytest.importorskip("yaml")
    f = tmp_path / "targets.yaml"
    f.write_text(
        "targets:\n  camera:\n    host: 192.0.2.50\n    user: pi\n",
        encoding="utf-8",
    )
    parsed = _pi_targets._default_file_loader(f)
    assert isinstance(parsed, dict)
    assert parsed["targets"]["camera"]["host"] == "192.0.2.50"


def test_default_file_loader_returns_none_for_empty_yaml(tmp_path):
    """Empty YAML files must yield None (not crash)."""
    pytest.importorskip("yaml")
    f = tmp_path / "empty.yaml"
    f.write_text("", encoding="utf-8")
    assert _pi_targets._default_file_loader(f) is None


def test_default_file_loader_raises_on_non_mapping_top_level(tmp_path):
    """Top-level lists/scalars must surface as ValueError, not silent None."""
    pytest.importorskip("yaml")
    f = tmp_path / "list.yaml"
    f.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        _pi_targets._default_file_loader(f)


def test_resolve_target_yaml_targets_not_a_mapping_falls_through_to_env():
    """``targets:`` keyed to a non-dict must fall through, not crash."""
    payload = {"targets": ["camera", "display"]}  # list, not mapping
    env = {"CAMERA_IP": "192.0.2.10"}
    target = resolve_target("camera", env=env, file_loader=_loader(payload))
    assert target == Target(host="192.0.2.10", user="ian")


def test_resolve_target_yaml_entry_not_a_mapping_falls_through_to_env():
    """An entry that is not a dict must fall through to env, not crash."""
    payload = {"targets": {"camera": "192.0.2.10"}}  # scalar entry
    env = {"CAMERA_IP": "10.0.0.1"}
    target = resolve_target("camera", env=env, file_loader=_loader(payload))
    assert target == Target(host="10.0.0.1", user="ian")


def test_resolve_target_yaml_entry_with_explicit_user():
    payload = {"targets": {"camera": {"host": "10.0.0.5", "user": "alice"}}}
    target = resolve_target("camera", env={}, file_loader=_loader(payload))
    assert target == Target(host="10.0.0.5", user="alice")


def test_resolve_target_yaml_entry_missing_user_uses_default():
    """YAML host present + missing user must fall back to _DEFAULT_USER."""
    payload = {"targets": {"camera": {"host": "10.0.0.5"}}}
    target = resolve_target("camera", env={}, file_loader=_loader(payload))
    assert target == Target(host="10.0.0.5", user="ian")
