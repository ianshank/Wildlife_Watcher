"""Unit tests for the paho v1/v2 client compatibility shims.

We have two parallel implementations:
- ``scripts/_mqtt_client.make_client`` (used by verify scripts and HIL tests)
- ``pi-display-node/kiosk/wildlife_kiosk._make_paho_client`` (kept inline so
  the kiosk package is self-contained on the Pi)

Both must:
1. Use the v2 ``CallbackAPIVersion.VERSION1`` signature when paho-mqtt 2.x
   is installed.
2. Fall back to the v1 keyword-only signature if v2 raises ``TypeError``
   (e.g. mocked paho where the v2 path is unavailable).
3. Skip the v2 branch entirely when ``CallbackAPIVersion`` is absent
   (paho-mqtt 1.6.x).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# Make scripts/ importable
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _mqtt_client import make_client as scripts_make_client  # type: ignore[import-not-found]  # noqa: E402,I001

import wildlife_kiosk  # noqa: E402


@pytest.fixture
def fake_paho_v2() -> Any:
    """A paho.mqtt.client stand-in that exposes a v2-style Client + CB enum."""
    fake = types.SimpleNamespace()

    class _CB:
        VERSION1 = "v1"
        VERSION2 = "v2"

    fake.CallbackAPIVersion = _CB

    class _Client:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    fake.Client = _Client
    return fake


@pytest.fixture
def fake_paho_v1() -> Any:
    """paho 1.6 style — no CallbackAPIVersion attribute at all."""
    fake = types.SimpleNamespace()

    class _Client:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    fake.Client = _Client
    return fake


@pytest.fixture
def fake_paho_v2_typeerror() -> Any:
    """v2-shaped paho whose Client(__init__) rejects v2 args (forces fallback)."""
    fake = types.SimpleNamespace()

    class _CB:
        VERSION1 = "v1"

    fake.CallbackAPIVersion = _CB
    calls: list[tuple[Any, ...]] = []

    class _Client:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs
            calls.append((args, kwargs))
            # Reject v2 positional arg; accept the v1 retry.
            if args and args[0] == "v1":
                raise TypeError("simulated v1.x signature")

    fake.Client = _Client
    fake._calls = calls
    return fake


# ---------------------------------------------------------------------------
# scripts/_mqtt_client.make_client
# ---------------------------------------------------------------------------


def test_scripts_make_client_v2_path(fake_paho_v2: Any) -> None:
    with mock.patch.object(sys.modules["_mqtt_client"], "mqtt", fake_paho_v2):
        c: Any = scripts_make_client("cid-a")
    assert c.args == ("v1",)
    assert c.kwargs == {"client_id": "cid-a", "clean_session": True}


def test_scripts_make_client_v1_path(fake_paho_v1: Any) -> None:
    with mock.patch.object(sys.modules["_mqtt_client"], "mqtt", fake_paho_v1):
        c: Any = scripts_make_client("cid-b", clean_session=False)
    assert c.args == ()
    assert c.kwargs == {"client_id": "cid-b", "clean_session": False}


def test_scripts_make_client_falls_back_on_typeerror(
    fake_paho_v2_typeerror: Any,
) -> None:
    with mock.patch.object(
        sys.modules["_mqtt_client"], "mqtt", fake_paho_v2_typeerror
    ):
        c: Any = scripts_make_client("cid-c")
    # Two calls happened: v2 (raises) then v1 (succeeds)
    assert len(fake_paho_v2_typeerror._calls) == 2
    assert c.args == ()
    assert c.kwargs == {"client_id": "cid-c", "clean_session": True}


def test_scripts_make_client_extra_kwargs(fake_paho_v2: Any) -> None:
    with mock.patch.object(sys.modules["_mqtt_client"], "mqtt", fake_paho_v2):
        c: Any = scripts_make_client("cid-d", clean_session=True, transport="tcp")
    assert c.kwargs == {
        "client_id": "cid-d",
        "clean_session": True,
        "transport": "tcp",
    }


# ---------------------------------------------------------------------------
# wildlife_kiosk._make_paho_client (inline copy)
# ---------------------------------------------------------------------------


def test_kiosk_make_paho_client_v2_path(fake_paho_v2: Any) -> None:
    with mock.patch.object(wildlife_kiosk, "mqtt", fake_paho_v2):
        c: Any = wildlife_kiosk._make_paho_client("kiosk-a")
    assert c.args == ("v1",)
    assert c.kwargs == {"client_id": "kiosk-a", "clean_session": True}


def test_kiosk_make_paho_client_v1_path(fake_paho_v1: Any) -> None:
    with mock.patch.object(wildlife_kiosk, "mqtt", fake_paho_v1):
        c: Any = wildlife_kiosk._make_paho_client("kiosk-b", clean_session=False)
    assert c.args == ()
    assert c.kwargs == {"client_id": "kiosk-b", "clean_session": False}


def test_kiosk_make_paho_client_typeerror_fallback(
    fake_paho_v2_typeerror: Any,
) -> None:
    with mock.patch.object(wildlife_kiosk, "mqtt", fake_paho_v2_typeerror):
        c: Any = wildlife_kiosk._make_paho_client("kiosk-c")
    assert len(fake_paho_v2_typeerror._calls) == 2
    assert c.args == ()
    assert c.kwargs == {"client_id": "kiosk-c", "clean_session": True}
