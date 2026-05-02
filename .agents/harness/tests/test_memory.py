from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import pytest
import runtime

pytestmark = pytest.mark.unit


def test_view_create_round_trip(memory_store: runtime.MemoryStore) -> None:
    memory_store.create(PurePosixPath("notes.md"), "hello\nworld\n")
    text = memory_store.view(PurePosixPath("notes.md"))
    assert text == "hello\nworld\n"


def test_view_line_range(memory_store: runtime.MemoryStore) -> None:
    memory_store.create(PurePosixPath("a.md"), "1\n2\n3\n4\n")
    chunk = memory_store.view(PurePosixPath("a.md"), line_range=(2, 3))
    assert chunk == "2\n3\n"


def test_create_rejects_existing_file(memory_store: runtime.MemoryStore) -> None:
    memory_store.create(PurePosixPath("dup.md"), "x")
    with pytest.raises(FileExistsError):
        memory_store.create(PurePosixPath("dup.md"), "y")


def test_insert_after_line(memory_store: runtime.MemoryStore) -> None:
    memory_store.create(PurePosixPath("p.md"), "a\nb\n")
    memory_store.insert(PurePosixPath("p.md"), after_line=1, content="X")
    assert memory_store.view(PurePosixPath("p.md")) == "a\nX\nb\n"


def test_str_replace_unique_only(memory_store: runtime.MemoryStore) -> None:
    memory_store.create(PurePosixPath("r.md"), "alpha beta alpha\n")
    with pytest.raises(ValueError):
        memory_store.str_replace(PurePosixPath("r.md"), "alpha", "z")


def test_str_replace_missing_raises(memory_store: runtime.MemoryStore) -> None:
    memory_store.create(PurePosixPath("r.md"), "alpha\n")
    with pytest.raises(KeyError):
        memory_store.str_replace(PurePosixPath("r.md"), "zeta", "z")


def test_delete_file_and_directory(memory_store: runtime.MemoryStore) -> None:
    memory_store.create(PurePosixPath("d.md"), "x")
    memory_store.delete(PurePosixPath("d.md"))
    with pytest.raises(FileNotFoundError):
        memory_store.view(PurePosixPath("d.md"))


def test_resolve_rejects_path_outside_root(memory_store: runtime.MemoryStore) -> None:
    with pytest.raises(ValueError):
        memory_store.view(PurePosixPath("../escape.md"))


def test_episodic_path_uses_clock(
    runtime_cfg: runtime.FullRuntimeConfig, memory_root: Path,
) -> None:
    moments = iter(
        [
            datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 5, 3, 10, 0, 0, tzinfo=timezone.utc),
        ]
    )
    store = runtime.MemoryStore(
        runtime_cfg.memory, root=memory_root, clock=lambda: next(moments),
    )
    p1 = store.append_episodic("first")
    p2 = store.append_episodic("second")
    assert p1.name == "2026-05-02.md"
    assert p2.name == "2026-05-03.md"


def test_index_update_and_atomic_replace(memory_store: runtime.MemoryStore) -> None:
    memory_store.update_index("- decision A")
    memory_store.update_index("- decision B")
    text = memory_store.view(PurePosixPath("MEMORY.md"))
    assert "decision A" in text and "decision B" in text


def test_rotate_archives_and_keeps_tail(
    runtime_cfg: runtime.FullRuntimeConfig, memory_root: Path,
    frozen_utc: Callable[[], datetime],
) -> None:
    # Tighten thresholds via a custom config.
    cfg = runtime.MemoryConfig(
        root=runtime_cfg.memory.root,
        index_file=runtime_cfg.memory.index_file,
        episodic_dir=runtime_cfg.memory.episodic_dir,
        spec_dir=runtime_cfg.memory.spec_dir,
        rotate_after_bytes=64,
        rotate_keep_tail_bytes=16,
        gc_heartbeat_iterations=2,
        atomic_write_suffix=".tmp",
    )
    store = runtime.MemoryStore(cfg, root=memory_root, clock=frozen_utc)
    big = "X" * 200
    store.update_index(big)
    archive = store.rotate_index()
    assert archive.exists()
    new_index = (memory_root / cfg.index_file).read_text()
    assert len(new_index.encode("utf-8")) <= cfg.rotate_keep_tail_bytes


def test_gc_heartbeat_only_fires_at_interval(
    runtime_cfg: runtime.FullRuntimeConfig, memory_root: Path,
    frozen_utc: Callable[[], datetime],
) -> None:
    cfg = runtime.MemoryConfig(
        root=runtime_cfg.memory.root,
        index_file=runtime_cfg.memory.index_file,
        episodic_dir=runtime_cfg.memory.episodic_dir,
        spec_dir=runtime_cfg.memory.spec_dir,
        rotate_after_bytes=64,
        rotate_keep_tail_bytes=16,
        gc_heartbeat_iterations=3,
        atomic_write_suffix=".tmp",
    )
    store = runtime.MemoryStore(cfg, root=memory_root, clock=frozen_utc)
    store.update_index("Y" * 200)
    assert store.gc_heartbeat(1) is False
    assert store.gc_heartbeat(2) is False
    assert store.gc_heartbeat(3) is True


def test_spec_shard_writes_three_files(memory_store: runtime.MemoryStore) -> None:
    shard = memory_store.write_spec_shard("2026-05-02-x", "spec body", "task body")
    assert (shard / "SPEC.md").read_text().startswith("spec body")
    assert (shard / "task.md").read_text().startswith("task body")
    assert (shard / "learnings.md").read_text().startswith("# Learnings")


def test_spec_shard_rejects_bad_id(memory_store: runtime.MemoryStore) -> None:
    with pytest.raises(ValueError):
        memory_store.write_spec_shard("bad/id", "s", "t")
    with pytest.raises(ValueError):
        memory_store.write_spec_shard("", "s", "t")
