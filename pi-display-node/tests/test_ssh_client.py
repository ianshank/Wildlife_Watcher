"""Unit tests for the shared paramiko SSH client factory.

The tests use a fake ``paramiko`` module patched into the helper's
namespace so we can assert which policies + host_keys functions get
invoked without touching the real SSH stack.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import cast
from unittest import mock

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _ssh_client  # noqa: E402


class _FakeClient:
    def __init__(self) -> None:
        self.system_loaded = False
        self.host_keys_paths: list[str] = []
        self.policy: object = None
        self.connect_kwargs: dict | None = None
        self._raise_on_load_host_keys = False

    def load_system_host_keys(self) -> None:
        self.system_loaded = True

    def load_host_keys(self, p: str) -> None:
        if self._raise_on_load_host_keys:
            raise OSError("nope")
        self.host_keys_paths.append(p)

    def set_missing_host_key_policy(self, policy) -> None:
        self.policy = policy

    def connect(self, host, **kw) -> None:
        self.connect_kwargs = {"host": host, **kw}


class _FakeRejectPolicy:
    pass


class _FakeAutoAddPolicy:
    pass


@pytest.fixture
def fake_paramiko(monkeypatch):
    fake = mock.MagicMock()
    fake.SSHClient = _FakeClient
    fake.RejectPolicy = _FakeRejectPolicy
    fake.AutoAddPolicy = _FakeAutoAddPolicy
    monkeypatch.setattr(_ssh_client, "paramiko", fake)
    return fake


def test_build_ssh_client_strict_default_uses_reject_policy(
    fake_paramiko, monkeypatch
):
    monkeypatch.delenv("PI_HOST_KEY_POLICY", raising=False)
    monkeypatch.delenv("PI_KNOWN_HOSTS", raising=False)
    c = cast(_FakeClient, _ssh_client.build_ssh_client())
    assert isinstance(c.policy, _FakeRejectPolicy)
    assert c.system_loaded is True


def test_build_ssh_client_auto_policy_when_env_set(fake_paramiko, monkeypatch):
    monkeypatch.setenv("PI_HOST_KEY_POLICY", "auto")
    c = cast(_FakeClient, _ssh_client.build_ssh_client())
    assert isinstance(c.policy, _FakeAutoAddPolicy)


def test_build_ssh_client_loads_known_hosts_when_present(
    fake_paramiko, monkeypatch, tmp_path
):
    kh = tmp_path / "known_hosts"
    kh.write_text("# fake")
    monkeypatch.setenv("PI_KNOWN_HOSTS", str(kh))
    c = cast(_FakeClient, _ssh_client.build_ssh_client())
    assert c.host_keys_paths == [str(kh)]


def test_build_ssh_client_skips_missing_known_hosts(
    fake_paramiko, monkeypatch, tmp_path
):
    monkeypatch.setenv("PI_KNOWN_HOSTS", str(tmp_path / "nope"))
    c = cast(_FakeClient, _ssh_client.build_ssh_client())
    assert c.host_keys_paths == []


def test_build_ssh_client_swallows_load_host_keys_failure(
    fake_paramiko, monkeypatch, tmp_path, caplog
):
    kh = tmp_path / "known_hosts"
    kh.write_text("# fake")
    monkeypatch.setenv("PI_KNOWN_HOSTS", str(kh))

    class _BoomClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self._raise_on_load_host_keys = True

    fake_paramiko.SSHClient = _BoomClient
    with caplog.at_level("WARNING"):
        c = cast(_FakeClient, _ssh_client.build_ssh_client())
    assert c.host_keys_paths == []  # raise prevented append
    assert any("Failed to load known_hosts" in m for m in caplog.messages)


def test_build_ssh_client_swallows_load_system_host_keys_failure(
    fake_paramiko, monkeypatch
):
    monkeypatch.delenv("PI_HOST_KEY_POLICY", raising=False)

    class _BoomClient(_FakeClient):
        def load_system_host_keys(self) -> None:
            raise OSError("system_host_keys missing")

    fake_paramiko.SSHClient = _BoomClient
    # Should not raise.
    c = cast(_FakeClient, _ssh_client.build_ssh_client())
    assert isinstance(c.policy, _FakeRejectPolicy)


def test_connect_passes_safe_defaults(fake_paramiko):
    c = _FakeClient()
    _ssh_client.connect(c, "host.example", "user", "pw")  # type: ignore[arg-type]
    assert c.connect_kwargs == {
        "host": "host.example",
        "username": "user",
        "password": "pw",
        "timeout": 10,
        "banner_timeout": 10,
        "auth_timeout": 10,
        "allow_agent": False,
        "look_for_keys": False,
    }


def test_connect_overrides(fake_paramiko):
    c = _FakeClient()
    _ssh_client.connect(c, "h", "u", "p", timeout=30, banner_timeout=5,  # type: ignore[arg-type]
                        auth_timeout=20)
    assert c.connect_kwargs is not None
    assert c.connect_kwargs["timeout"] == 30
    assert c.connect_kwargs["banner_timeout"] == 5
    assert c.connect_kwargs["auth_timeout"] == 20


def test_connect_with_key_only_uses_pubkey_auth(fake_paramiko):
    """key_filename without password: agent + key lookup must be enabled."""
    c = _FakeClient()
    _ssh_client.connect(
        cast(_ssh_client.paramiko.SSHClient, c),
        "h", "u", key_filename="/tmp/id_ed25519",
    )
    assert c.connect_kwargs is not None
    assert c.connect_kwargs["key_filename"] == "/tmp/id_ed25519"
    assert c.connect_kwargs["password"] is None
    assert c.connect_kwargs["allow_agent"] is True
    assert c.connect_kwargs["look_for_keys"] is True


def test_connect_with_password_only_keeps_legacy_safe_defaults(fake_paramiko):
    c = _FakeClient()
    _ssh_client.connect(c, "h", "u", "pw")  # type: ignore[arg-type]
    assert c.connect_kwargs is not None
    assert "key_filename" not in c.connect_kwargs
    assert c.connect_kwargs["password"] == "pw"
    assert c.connect_kwargs["allow_agent"] is False
    assert c.connect_kwargs["look_for_keys"] is False


def test_connect_with_both_password_and_key_uses_key_path(fake_paramiko):
    """Encrypted-key flow: both supplied -> key_filename path wins, password
    is still threaded through so paramiko can decrypt the key."""
    c = _FakeClient()
    _ssh_client.connect(
        cast(_ssh_client.paramiko.SSHClient, c),
        "h", "u", "pw", key_filename="/tmp/id_ed25519",
    )
    assert c.connect_kwargs is not None
    assert c.connect_kwargs["key_filename"] == "/tmp/id_ed25519"
    assert c.connect_kwargs["password"] == "pw"
    assert c.connect_kwargs["allow_agent"] is True
    assert c.connect_kwargs["look_for_keys"] is True


def test_connect_without_password_or_key_raises(fake_paramiko):
    c = _FakeClient()
    with pytest.raises(ValueError, match="key_filename"):
        _ssh_client.connect(c, "h", "u")  # type: ignore[arg-type]
