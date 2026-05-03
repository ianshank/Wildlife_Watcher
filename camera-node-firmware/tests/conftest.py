"""Conftest for camera-node HIL integration tests.

Spins up an embedded MQTT broker (amqtt) so no external Mosquitto is needed,
then optionally compiles + flashes the firmware to the attached ESP32S3.
"""
# pyright: reportMissingTypeStubs=false
from __future__ import annotations

import asyncio
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt  # pyright: ignore[reportMissingTypeStubs, reportMissingImports]
import pytest


def _make_client(client_id: str) -> mqtt.Client:
    """Construct a paho.mqtt.Client compatible with both 1.6.x and 2.x.

    paho-mqtt 2.0 added a required ``CallbackAPIVersion`` positional arg.
    We try the v2 signature first and fall back to the v1 one.
    """
    cb_api = getattr(mqtt, "CallbackAPIVersion", None)
    if cb_api is not None:
        try:
            return mqtt.Client(cb_api.VERSION1, client_id=client_id, clean_session=True)
        except TypeError:
            pass
    return mqtt.Client(client_id=client_id, clean_session=True)


# ---------------------------------------------------------------------------
# Configuration (overridable via env vars)
# ---------------------------------------------------------------------------
BROKER_HOST = os.environ.get("MQTT_BROKER", "127.0.0.1")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
NODE_ID = os.environ.get("NODE_ID", "test-camera-1")


# ---------------------------------------------------------------------------
# Embedded MQTT broker (amqtt) — runs for the entire test session
# ---------------------------------------------------------------------------
def _run_broker(loop: asyncio.AbstractEventLoop, started: threading.Event) -> None:
    """Target for the broker background thread."""
    asyncio.set_event_loop(loop)

    async def _start() -> None:
        from amqtt.broker import Broker  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]  # local import to keep top-level fast

        config = {
            "listeners": {
                "default": {
                    "type": "tcp",
                    "bind": f"{BROKER_HOST}:{BROKER_PORT}",
                    "max_connections": 50,
                },
            },
            "sys_interval": 0,
            "auth": {
                "allow-anonymous": True,
                "plugins": ["auth_anonymous"],
            },
        }
        broker = Broker(config)
        await broker.start()
        started.set()
        # Keep the broker alive until the loop is stopped
        while True:
            await asyncio.sleep(1)

    loop.run_until_complete(_start())


@pytest.fixture(scope="session")
def embedded_broker():
    """Start an in-process MQTT broker for the duration of the test session."""
    loop = asyncio.new_event_loop()
    started = threading.Event()
    t = threading.Thread(target=_run_broker, args=(loop, started), daemon=True)
    t.start()

    # Wait for the broker to be ready (up to 10 s)
    if not started.wait(timeout=10):
        pytest.fail("Embedded MQTT broker failed to start within 10 seconds.")

    print(f"\n[conftest] Embedded MQTT broker listening on {BROKER_HOST}:{BROKER_PORT}")
    yield

    # Teardown: stop the event loop (daemon thread will exit)
    loop.call_soon_threadsafe(loop.stop)
    t.join(timeout=5)
    print("[conftest] Embedded MQTT broker stopped.")


# ---------------------------------------------------------------------------
# Firmware flash fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def flash_firmware(embedded_broker):
    """Compile and flash the firmware to the attached ESP32S3 via PlatformIO."""
    if os.environ.get("FLASH_FIRMWARE", "0") != "1":
        print("\n[conftest] FLASH_FIRMWARE != 1, skipping compile+flash.")
        yield
        return

    print("\n[conftest] Compiling and flashing firmware to the device...")
    secrets_path = Path("include/secrets.h")
    if not secrets_path.exists():
        secrets_path.write_text(
            f'#pragma once\n'
            f'#define WIFI_SSID "YOUR_SSID"\n'
            f'#define WIFI_PASSWORD "YOUR_PASSWORD"\n'
            f'#define MQTT_BROKER "{BROKER_HOST}"\n'
            f'#define MQTT_PORT {BROKER_PORT}\n'
            f'#define MQTT_USER ""\n'
            f'#define MQTT_PASSWORD ""\n'
            f'#define NODE_ID "{NODE_ID}"\n',
            encoding="utf-8",
        )
        print("[conftest] Created temporary include/secrets.h")

    try:
        result = subprocess.run(
            ["pio", "run", "-t", "upload"],
            cwd=".",
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            pytest.fail(
                f"Firmware flash failed:\n{result.stderr}\n{result.stdout}"
            )
        print("[conftest] Flash successful.")
    except FileNotFoundError:
        pytest.fail("PlatformIO (pio) not found in PATH.")

    # Give the device a few seconds to boot after flash
    time.sleep(5)
    yield
    print("\n[conftest] Test session complete.")


# ---------------------------------------------------------------------------
# MQTT subscriber client fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def mqtt_client(flash_firmware):
    """Paho MQTT client connected to the embedded broker, listening to wildlife/#."""
    msg_queue: queue.Queue[mqtt.MQTTMessage] = queue.Queue()

    def on_connect(
        client: mqtt.Client,
        userdata: object,
        flags: dict,
        rc: int,
    ) -> None:
        if rc == 0:
            client.subscribe("wildlife/#")
        else:
            print(f"[mqtt] Connection failed with code {rc}")

    def on_message(
        client: mqtt.Client,
        userdata: object,
        msg: mqtt.MQTTMessage,
    ) -> None:
        msg_queue.put(msg)

    client = _make_client("pytest-harness")
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_start()
    except Exception as exc:
        pytest.fail(f"Could not connect to MQTT broker: {exc}")

    yield client, msg_queue

    client.loop_stop()
    client.disconnect()
