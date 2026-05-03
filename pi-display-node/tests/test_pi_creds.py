"""Unit tests for ``scripts/_pi_creds.Credentials``.

Tests use only in-memory env mappings + injected file_loader (via
``_pi_targets``) so they run hermetically without a real ``~/.wildlife``
directory or PyYAML import.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable (conftest already adds it but be defensive).
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _pi_creds  # noqa: E402
from _pi_creds import Credentials  # noqa: E402


def test_load_from_env_uses_pi_targets_for_host_and_user(monkeypatch):
    env = {"PI_HOST": "10.0.0.5", "PI_USER": "alice", "PI_PASS": "secret"}
    creds = Credentials.load_from_env(env=env)
    assert creds.host == "10.0.0.5"
    assert creds.user == "alice"
    assert creds.password == "secret"
    assert creds.key_path is None


def test_load_from_env_with_key_only_returns_none_password():
    env = {"PI_HOST": "10.0.0.5", "PI_USER": "alice", "PI_KEY": "/k/id_ed25519"}
    creds = Credentials.load_from_env(env=env)
    assert creds.password is None
    assert creds.key_path == "/k/id_ed25519"


def test_load_from_env_with_both_password_and_key():
    env = {
        "PI_HOST": "10.0.0.5",
        "PI_USER": "alice",
        "PI_PASS": "p",
        "PI_KEY": "/k/id",
    }
    creds = Credentials.load_from_env(env=env)
    assert creds.password == "p"
    assert creds.key_path == "/k/id"


def test_load_from_env_raises_when_neither_password_nor_key_is_set():
    env = {"PI_HOST": "10.0.0.5", "PI_USER": "alice"}
    with pytest.raises(RuntimeError, match="PI_PASS or PI_KEY"):
        Credentials.load_from_env(env=env)


def test_load_from_env_raises_when_no_target_source_configured():
    # No PI_HOST and no PI_TARGETS_FILE entry: resolve_target("display") raises.
    env: dict[str, str] = {"PI_PASS": "p"}
    with pytest.raises(RuntimeError, match="Cannot resolve Pi target 'display'"):
        Credentials.load_from_env(env=env)


def test_as_legacy_tuple_returns_host_user_password():
    creds = Credentials(host="h", user="u", password="p", key_path=None)
    assert creds.as_legacy_tuple() == ("h", "u", "p")


def test_as_legacy_tuple_raises_when_password_missing():
    creds = Credentials(host="h", user="u", password=None, key_path="/k/id")
    with pytest.raises(RuntimeError, match="requires a password"):
        creds.as_legacy_tuple()


def test_load_legacy_returns_three_tuple(monkeypatch):
    monkeypatch.setenv("PI_HOST", "10.0.0.99")
    monkeypatch.setenv("PI_USER", "bob")
    monkeypatch.setenv("PI_PASS", "pw123")
    # Ensure PI_TARGETS_FILE doesn't accidentally point at a real file.
    monkeypatch.setenv("PI_TARGETS_FILE", "/nonexistent/wildlife-targets.yaml")
    host, user, pw = _pi_creds.load()
    assert (host, user, pw) == ("10.0.0.99", "bob", "pw123")


def test_load_legacy_exits_when_pi_pass_missing(monkeypatch, capsys):
    monkeypatch.setenv("PI_HOST", "10.0.0.99")
    monkeypatch.setenv("PI_USER", "bob")
    monkeypatch.delenv("PI_PASS", raising=False)
    monkeypatch.delenv("PI_KEY", raising=False)
    monkeypatch.setenv("PI_TARGETS_FILE", "/nonexistent/wildlife-targets.yaml")
    with pytest.raises(SystemExit) as excinfo:
        _pi_creds.load()
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "PI_PASS" in err


def test_load_legacy_allows_key_only(monkeypatch):
    """PI_KEY without PI_PASS must succeed and return empty password."""
    monkeypatch.setenv("PI_HOST", "10.0.0.99")
    monkeypatch.setenv("PI_USER", "bob")
    monkeypatch.delenv("PI_PASS", raising=False)
    monkeypatch.setenv("PI_KEY", "/home/bob/.ssh/id_ed25519")
    monkeypatch.setenv("PI_TARGETS_FILE", "/nonexistent/wildlife-targets.yaml")
    host, user, pw = _pi_creds.load()
    assert (host, user, pw) == ("10.0.0.99", "bob", "")
