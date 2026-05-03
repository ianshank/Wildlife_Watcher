"""Reusable paho-mqtt client factory.

paho-mqtt 2.0 added a required ``CallbackAPIVersion`` positional argument
to ``mqtt.Client(...)``. Several places in this repo (camera-node tests,
the kiosk MQTT bridge, and the various ``scripts/verify_*`` utilities)
need to construct a client and previously each carried its own
try/except v1/v2 compatibility shim. This module is the single source of
truth for that compatibility logic.

Usage::

    from _mqtt_client import make_client
    client = make_client("my-client-id")
    client.username_pw_set(user, pw)
    client.connect(host, port, keepalive)
"""
from __future__ import annotations

import logging
from typing import Any

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


def make_client(
    client_id: str,
    *,
    clean_session: bool = True,
    **extra: Any,
) -> mqtt.Client:
    """Return a ``paho.mqtt.Client`` that works on both v1.x and v2.x.

    Parameters
    ----------
    client_id:
        MQTT client identifier (must be unique per broker session).
    clean_session:
        Pass-through to paho. Defaults to True for stateless callers.
    extra:
        Forwarded to ``mqtt.Client(...)`` for both v1 and v2 paths.
    """
    cb_api = getattr(mqtt, "CallbackAPIVersion", None)
    if cb_api is not None:
        # Build a single kwargs dict so no explicit keyword can clash with **extra.
        # Explicit parameters shadow any accidental duplicate in extra.
        merged: dict[str, Any] = dict(extra)
        merged["client_id"] = client_id
        merged["clean_session"] = clean_session
        try:
            return mqtt.Client(cb_api.VERSION1, **merged)
        except TypeError:
            log.debug(
                "paho v2 signature rejected for client_id=%s; falling back to v1",
                client_id,
            )
    return mqtt.Client(
        client_id=client_id,
        clean_session=clean_session,
        **extra,
    )
