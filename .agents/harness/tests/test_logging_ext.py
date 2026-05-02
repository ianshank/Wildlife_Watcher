from __future__ import annotations

import io
import json
import logging

import pytest
import runtime
from runtime.logging_ext import ENV_FORMAT_KEY, JSON_FORMAT_VALUE, ROOT_LOGGER_NAME

pytestmark = pytest.mark.unit


def test_default_format_unchanged_when_env_unset(
    runtime_cfg: runtime.FullRuntimeConfig,
) -> None:
    stream = io.StringIO()
    runtime.install_runtime_logging(
        runtime_cfg.logging,
        env={},
        stream=stream,
        correlation_prefix=runtime_cfg.runtime.correlation_prefix,
    )
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    json_handlers = [h for h in logger.handlers if isinstance(h.formatter, runtime.JsonFormatter)]
    assert json_handlers == []


def test_json_format_emitted_when_env_set(
    runtime_cfg: runtime.FullRuntimeConfig,
) -> None:
    stream = io.StringIO()
    correlation = runtime.install_runtime_logging(
        runtime_cfg.logging,
        env={ENV_FORMAT_KEY: JSON_FORMAT_VALUE},
        stream=stream,
        correlation_prefix=runtime_cfg.runtime.correlation_prefix,
    )
    logger = runtime.get_runtime_logger("logging_test")
    logger.setLevel(logging.INFO)
    cid = correlation.new_correlation_id()
    with correlation.bind(correlation_id=cid, task="t", iteration=1):
        logger.info("hello")
    line = stream.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)
    for field in runtime_cfg.logging.json_fields:
        if field in {"correlation_id", "task", "iteration"}:
            assert payload[field] is not None
        else:
            assert field in payload


def test_install_is_idempotent(runtime_cfg: runtime.FullRuntimeConfig) -> None:
    a = runtime.install_runtime_logging(
        runtime_cfg.logging,
        env={ENV_FORMAT_KEY: JSON_FORMAT_VALUE},
        stream=io.StringIO(),
    )
    b = runtime.install_runtime_logging(
        runtime_cfg.logging,
        env={ENV_FORMAT_KEY: JSON_FORMAT_VALUE},
        stream=io.StringIO(),
    )
    assert a is b


def test_correlation_ids_unique_and_prefixed(
    runtime_cfg: runtime.FullRuntimeConfig,
) -> None:
    correlation = runtime.CorrelationFilter(
        runtime_cfg.runtime.correlation_prefix,
        clock=lambda: 0.0,
    )
    ids = {correlation.new_correlation_id() for _ in range(50)}
    assert len(ids) == 50
    for cid in ids:
        assert cid.startswith(runtime_cfg.runtime.correlation_prefix + "-")


def test_bind_context_propagates_to_records(
    runtime_cfg: runtime.FullRuntimeConfig,
) -> None:
    correlation = runtime.CorrelationFilter(
        runtime_cfg.runtime.correlation_prefix,
        clock=lambda: 1.0,
    )
    record = logging.LogRecord(
        name="x", level=logging.INFO, pathname=__file__, lineno=1,
        msg="m", args=(), exc_info=None,
    )
    with correlation.bind(correlation_id="abc", task="t1"):
        correlation.filter(record)
    assert getattr(record, "correlation_id", None) == "abc"
    assert getattr(record, "task", None) == "t1"
