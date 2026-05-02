"""Structured-logging extension for the agent harness runtime.

Default text format from ``orchestrator.configure_logging`` is preserved when
``WILDLIFE_HARNESS_LOG_FORMAT`` is unset. Setting it to ``json`` swaps the
formatter on the ``wildlife_harness`` logger and attaches a
:class:`CorrelationFilter` so every record carries a stable correlation id and
optional context fields.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, TextIO

from .config import LoggingConfig

ROOT_LOGGER_NAME = "wildlife_harness"
RUNTIME_LOGGER_NAME = f"{ROOT_LOGGER_NAME}.runtime"
ENV_FORMAT_KEY = "WILDLIFE_HARNESS_LOG_FORMAT"
JSON_FORMAT_VALUE = "json"
INSTALL_FLAG = "_wildlife_runtime_logging_installed"


class CorrelationFilter(logging.Filter):
    """Inject a correlation id and any bound context fields into log records."""

    def __init__(
        self,
        prefix: str,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(name="")
        self._prefix = prefix
        self._clock = clock
        self._counter = 0
        self._stack: list[dict[str, Any]] = []

    def new_correlation_id(self) -> str:
        self._counter += 1
        return f"{self._prefix}-{int(self._clock() * 1_000_000)}-{self._counter:04d}"

    @contextlib.contextmanager
    def bind(self, **fields: Any) -> Iterator[None]:
        self._stack.append(dict(fields))
        try:
            yield
        finally:
            self._stack.pop()

    def _current(self) -> Mapping[str, Any]:
        merged: dict[str, Any] = {}
        for layer in self._stack:
            merged.update(layer)
        return merged

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in self._current().items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    """Serialize log records as JSON limited to the configured field allowlist."""

    def __init__(self, fields: Sequence[str]) -> None:
        super().__init__()
        self._fields = tuple(fields)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {}
        for field in self._fields:
            if field == "ts":
                payload[field] = self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z")
            elif field == "level":
                payload[field] = record.levelname
            elif field == "logger":
                payload[field] = record.name
            elif field == "msg":
                payload[field] = record.getMessage()
            else:
                value = record.__dict__.get(field)
                if value is not None:
                    payload[field] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def install_runtime_logging(
    cfg: LoggingConfig,
    *,
    env: Mapping[str, str] | None = None,
    stream: TextIO | None = None,
    correlation_prefix: str = "ww",
    clock: Callable[[], float] = time.monotonic,
) -> CorrelationFilter:
    """Idempotently install the correlation filter and (optionally) JSON format.

    The default text format is unchanged unless ``env[ENV_FORMAT_KEY]`` equals
    ``"json"``. Returns the :class:`CorrelationFilter` so callers can mint
    correlation ids and bind contextual fields.
    """

    environment = env if env is not None else os.environ
    logger = logging.getLogger(ROOT_LOGGER_NAME)

    existing = getattr(logger, INSTALL_FLAG, None)
    if isinstance(existing, CorrelationFilter):
        return existing

    correlation = CorrelationFilter(correlation_prefix, clock=clock)
    logger.addFilter(correlation)

    if environment.get(ENV_FORMAT_KEY, "").lower() == JSON_FORMAT_VALUE:
        formatter = JsonFormatter(cfg.json_fields)
        handler: logging.Handler = (
            logging.StreamHandler(stream) if stream else logging.StreamHandler()
        )
        handler.setFormatter(formatter)
        handler.addFilter(correlation)
        logger.addHandler(handler)
        logger.propagate = False
    setattr(logger, INSTALL_FLAG, correlation)
    return correlation


def get_runtime_logger(suffix: str | None = None) -> logging.Logger:
    name = RUNTIME_LOGGER_NAME if not suffix else f"{RUNTIME_LOGGER_NAME}.{suffix}"
    return logging.getLogger(name)
