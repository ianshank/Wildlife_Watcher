from typing import Any

# Permissive stub for paho-mqtt 1.6.x and 2.x. The real runtime API differs
# between versions (notably the CallbackAPIVersion argument added in 2.0).
# We type the public surface as Any so the kiosk and the integration tests
# can use whichever shape the installed paho version exposes; runtime code
# is responsible for guarding the version differences explicitly.

class MQTTMessage:
    topic: str
    payload: bytes
    qos: int
    retain: bool

class MQTTMessageInfo:
    rc: int
    mid: int
    def wait_for_publish(self, timeout: float | None = ...) -> None: ...
    def is_published(self) -> bool: ...

class CallbackAPIVersion:
    VERSION1: Any
    VERSION2: Any

class Client:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def __setattr__(self, name: str, value: Any) -> None: ...
