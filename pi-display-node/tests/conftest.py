import asyncio
import contextlib
import socket
import sqlite3
import threading
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "pi-display-node" / "schema" / "observations.sql"


class MockMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


def initialize_db_schema(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def _reserve_tcp_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _run_broker(
    loop: asyncio.AbstractEventLoop,
    host: str,
    port: int,
    started: threading.Event,
    stop_requested: threading.Event,
    startup_errors: list[BaseException],
) -> None:
    asyncio.set_event_loop(loop)

    async def _main() -> None:
        from amqtt.broker import Broker  # local import keeps non-integration collection fast

        config = {
            "listeners": {
                "default": {
                    "type": "tcp",
                    "bind": f"{host}:{port}",
                    "max_connections": 20,
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
        try:
            while not stop_requested.is_set():
                await asyncio.sleep(0.1)
        finally:
            await broker.shutdown()

    try:
        loop.run_until_complete(_main())
    except BaseException as exc:  # pragma: no cover - only exercised on broker startup failure
        startup_errors.append(exc)
        started.set()
    finally:
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        with contextlib.suppress(Exception):
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


@pytest.fixture(scope="session")
def embedded_broker() -> Generator[dict[str, int | str], None, None]:
    host = "127.0.0.1"
    port = _reserve_tcp_port(host)
    loop = asyncio.new_event_loop()
    started = threading.Event()
    stop_requested = threading.Event()
    startup_errors: list[BaseException] = []
    thread = threading.Thread(
        target=_run_broker,
        args=(loop, host, port, started, stop_requested, startup_errors),
        daemon=True,
    )
    thread.start()

    if not started.wait(timeout=10):
        pytest.fail("Embedded MQTT broker failed to start within 10 seconds.")
    if startup_errors:
        pytest.fail(f"Embedded MQTT broker failed to start: {startup_errors[0]}")

    yield {"host": host, "port": port}

    stop_requested.set()
    loop.call_soon_threadsafe(lambda: None)
    thread.join(timeout=5)


@pytest.fixture
def broker_test_config(test_config, embedded_broker):
    test_config["mqtt"]["host"] = str(embedded_broker["host"])
    test_config["mqtt"]["port"] = int(embedded_broker["port"])
    test_config["mqtt"]["username"] = ""
    test_config["mqtt"]["password"] = ""
    return test_config


@pytest.fixture
def broker_publisher(embedded_broker):
    """Yields a long-lived paho publisher bound to the embedded broker.

    Using a single connection (instead of `paho.mqtt.publish.single` which
    opens/closes a TCP socket per call) avoids broker-side connection-reset
    races that surface when the full test suite runs the integration tests
    after other tests have churned through the embedded broker.
    """

    import sys
    from pathlib import Path

    _scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))
    from _mqtt_client import make_client  # type: ignore

    client = make_client("wildlife-test-publisher")
    client.connect(str(embedded_broker["host"]), int(embedded_broker["port"]), keepalive=30)
    client.loop_start()
    try:
        yield client
    finally:
        client.loop_stop()
        client.disconnect()


@pytest.fixture
def test_config(tmp_path):
    cfg = {
        "mqtt": {
            "client_id": "test-client",
            "host": "localhost",
            "port": 1883,
            "keepalive": 60,
            "username": "test",
            "password": "test",
            "topics": {
                "detections": "wildlife/detections/+",
                "thumbs": "wildlife/thumbs/+/+",
                "status": "wildlife/status/+",
            },
        },
        "ui": {
            "fullscreen": False,
            "screen_width": 800,
            "screen_height": 480,
            "thumb_grid_cols": 2,
            "thumb_grid_rows": 2,
            "max_feed_rows": 10,
            "min_confidence_to_show": 0.5,
            "refresh_ms": 100,
            "classes_to_highlight": ["bird"],
        },
    }
    cfg_file = tmp_path / "config.yaml"
    with cfg_file.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f)
    return cfg


@pytest.fixture
def mock_db_path(tmp_path):
    db_path = tmp_path / "test.db"

    initialize_db_schema(db_path)
    return db_path
