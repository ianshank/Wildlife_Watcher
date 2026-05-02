from __future__ import annotations

from pathlib import Path

import pytest
import runtime

pytestmark = pytest.mark.unit


def test_annotate_render_round_trip(runtime_cfg: runtime.FullRuntimeConfig) -> None:
    editor = runtime.HashAnchoredEditor(runtime_cfg.edits)
    text = "alpha\nbeta\ngamma\n"
    anchored = editor.annotate(text)
    assert [a.line_no for a in anchored] == [1, 2, 3, 4]  # trailing newline yields empty 4th
    rendered = editor.render(anchored)
    assert rendered.startswith("alpha\nbeta\ngamma")


def test_annotate_normalizes_crlf(runtime_cfg: runtime.FullRuntimeConfig) -> None:
    editor = runtime.HashAnchoredEditor(runtime_cfg.edits)
    a = editor.annotate("a\r\nb\r\nc")
    b = editor.annotate("a\nb\nc")
    assert [x.digest for x in a] == [x.digest for x in b]


def test_apply_edit_writes_when_anchors_match(
    runtime_cfg: runtime.FullRuntimeConfig, tmp_path: Path,
) -> None:
    target = tmp_path / "f.txt"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    editor = runtime.HashAnchoredEditor(runtime_cfg.edits)
    expected = editor.annotate(target.read_text())
    replacement = editor.annotate("ONE\ntwo\nthree\n")
    editor.apply_edit(target, expected=expected, replacement=replacement)
    assert target.read_text().splitlines()[0] == "ONE"


def test_apply_edit_aborts_on_mismatch(
    runtime_cfg: runtime.FullRuntimeConfig, tmp_path: Path,
) -> None:
    target = tmp_path / "f.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    editor = runtime.HashAnchoredEditor(runtime_cfg.edits)
    stale = editor.annotate("one\nDIFFERENT\n")
    new = editor.annotate("ONE\nTWO\n")
    with pytest.raises(runtime.HashMismatchError):
        editor.apply_edit(target, expected=stale, replacement=new)
    # File untouched.
    assert target.read_text() == "one\ntwo\n"


def test_warn_mode_writes_anyway(tmp_path: Path) -> None:
    cfg = runtime.EditsConfig(hash_algo="sha256", hash_prefix_length=8, mismatch_behavior="warn")
    editor = runtime.HashAnchoredEditor(cfg)
    target = tmp_path / "f.txt"
    target.write_text("a\n", encoding="utf-8")
    stale = editor.annotate("DIFFERENT\n")
    new = editor.annotate("Z\n")
    editor.apply_edit(target, expected=stale, replacement=new)
    assert target.read_text().startswith("Z")


def test_apply_edit_handles_empty_replacement(
    runtime_cfg: runtime.FullRuntimeConfig, tmp_path: Path,
) -> None:
    target = tmp_path / "f.txt"
    target.write_text("\n", encoding="utf-8")
    editor = runtime.HashAnchoredEditor(runtime_cfg.edits)
    expected = editor.annotate(target.read_text())
    editor.apply_edit(target, expected=expected, replacement=[])
    assert target.read_text() == ""
