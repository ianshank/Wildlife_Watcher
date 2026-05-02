from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
import runtime

pytestmark = pytest.mark.unit


def test_echo_model_emits_scripted_turns(
    echo_model_factory: Callable[..., runtime.EchoModel],
) -> None:
    turns = [
        runtime.ModelTurn(rationale="r1", tool_calls=(), final=False),
        runtime.ModelTurn(
            rationale="r2",
            tool_calls=(runtime.ToolCall(name="t", arguments={"k": 1}),),
            final=True,
        ),
    ]
    model = echo_model_factory(turns)
    a = model.reason(system="s", history=[], tools=[])
    b = model.reason(system="s", history=[], tools=[])
    assert a.rationale == "r1" and not a.final
    assert b.tool_calls[0].name == "t" and b.final


def test_echo_model_raises_when_exhausted(
    echo_model_factory: Callable[..., runtime.EchoModel],
) -> None:
    model = echo_model_factory([runtime.ModelTurn(rationale="x", tool_calls=(), final=True)])
    model.reason(system="", history=[], tools=[])
    with pytest.raises(IndexError):
        model.reason(system="", history=[], tools=[])


def test_local_command_model_parses_stdout(
    safe_runner_factory: Callable[..., runtime.SafeRunner], tmp_path: Path,
) -> None:
    payload = json.dumps(
        {
            "rationale": "ok",
            "tool_calls": [{"name": "fs.view", "arguments": {"path": "x"}}],
            "final": True,
        }
    ).encode()
    runner = safe_runner_factory(outputs=(payload, b""), returncode=0)
    model = runtime.LocalCommandModel(runner, command=["python", "-c", "print()"], cwd=tmp_path)
    turn = model.reason(system="s", history=[], tools=[])
    assert turn.final is True
    assert turn.tool_calls[0].name == "fs.view"
    assert turn.tool_calls[0].arguments["path"] == "x"


def test_local_command_model_handles_failure(
    safe_runner_factory: Callable[..., runtime.SafeRunner], tmp_path: Path,
) -> None:
    runner = safe_runner_factory(outputs=(b"", b"boom"), returncode=2)
    model = runtime.LocalCommandModel(runner, command=["false"], cwd=tmp_path)
    turn = model.reason(system="", history=[], tools=[])
    assert turn.tool_calls == ()
    assert turn.final is False
    assert "rc=2" in turn.rationale


def test_local_command_model_handles_bad_json(
    safe_runner_factory: Callable[..., runtime.SafeRunner], tmp_path: Path,
) -> None:
    runner = safe_runner_factory(outputs=(b"not json", b""), returncode=0)
    model = runtime.LocalCommandModel(runner, command=["echo"], cwd=tmp_path)
    turn = model.reason(system="", history=[], tools=[])
    assert turn.tool_calls == ()
    assert turn.final is False
