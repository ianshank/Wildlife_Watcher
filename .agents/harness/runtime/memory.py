"""Tiered Markdown memory store.

Implements the article's surgical memory tools (view/create/insert/str-replace/
delete), atomic writes via ``os.replace``, episodic logs at
``episodic/YYYY-MM-DD.md``, an index file (default ``MEMORY.md``), rotation,
GC heartbeat, and SPEC shard scaffolding.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Protocol

from .config import MemoryConfig
from .logging_ext import get_runtime_logger


class FileOps(Protocol):
    def read_text(self, path: Path) -> str: ...
    def write_text(self, path: Path, content: str) -> None: ...
    def replace(self, src: Path, dst: Path) -> None: ...
    def exists(self, path: Path) -> bool: ...
    def mkdir(self, path: Path, *, parents: bool, exist_ok: bool) -> None: ...
    def remove(self, path: Path) -> None: ...
    def rmtree(self, path: Path) -> None: ...
    def iter_dir(self, path: Path) -> Iterable[Path]: ...
    def stat_size(self, path: Path) -> int: ...


@dataclass(frozen=True)
class _RealFileOps:
    """Default :class:`FileOps` backed by ``pathlib`` and ``os``."""

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def replace(self, src: Path, dst: Path) -> None:
        src.replace(dst)

    def exists(self, path: Path) -> bool:
        return path.exists()

    def mkdir(self, path: Path, *, parents: bool, exist_ok: bool) -> None:
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def remove(self, path: Path) -> None:
        path.unlink()

    def rmtree(self, path: Path) -> None:
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()
            else:
                child.unlink()
        path.rmdir()

    def iter_dir(self, path: Path) -> Iterable[Path]:
        return list(path.iterdir())

    def stat_size(self, path: Path) -> int:
        return path.stat().st_size


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStore:
    def __init__(
        self,
        cfg: MemoryConfig,
        *,
        root: Path,
        clock: Callable[[], datetime] = _utc_now,
        file_ops: FileOps | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._root = root
        self._clock = clock
        self._fops: FileOps = file_ops or _RealFileOps()
        self._logger = logger or get_runtime_logger("memory")
        self._fops.mkdir(self._root, parents=True, exist_ok=True)
        self._fops.mkdir(self._episodic_root, parents=True, exist_ok=True)
        self._fops.mkdir(self._spec_root, parents=True, exist_ok=True)
        if not self._fops.exists(self.index_path):
            self._atomic_write(self.index_path, "# MEMORY index\n")

    # ------------------------------------------------------------------
    # path helpers
    # ------------------------------------------------------------------
    @property
    def root(self) -> Path:
        return self._root

    @property
    def index_path(self) -> Path:
        return self._root / self._cfg.index_file

    @property
    def _episodic_root(self) -> Path:
        return self._root / self._cfg.episodic_dir

    @property
    def _spec_root(self) -> Path:
        return self._root / self._cfg.spec_dir

    def _resolve(self, rel: PurePosixPath) -> Path:
        candidate = (self._root / Path(*rel.parts)).resolve()
        root_resolved = self._root.resolve()
        if root_resolved not in candidate.parents and candidate != root_resolved:
            raise ValueError(f"Refusing to access path outside memory root: {rel}")
        return candidate

    def _atomic_write(self, path: Path, content: str) -> None:
        tmp = path.with_suffix(path.suffix + self._cfg.atomic_write_suffix)
        self._fops.mkdir(path.parent, parents=True, exist_ok=True)
        self._fops.write_text(tmp, content)
        self._fops.replace(tmp, path)

    # ------------------------------------------------------------------
    # surgical tools
    # ------------------------------------------------------------------
    def view(
        self,
        path: PurePosixPath,
        *,
        line_range: tuple[int, int] | None = None,
    ) -> str:
        target = self._resolve(path)
        if not self._fops.exists(target):
            raise FileNotFoundError(target)
        text = self._fops.read_text(target)
        lines = text.splitlines(keepends=True)
        if line_range is None:
            return text
        start, end = line_range
        if start < 1 or end < start or end > len(lines):
            raise ValueError(f"Invalid line_range {line_range} for file with {len(lines)} lines")
        return "".join(lines[start - 1 : end])

    def create(self, path: PurePosixPath, content: str) -> None:
        target = self._resolve(path)
        if self._fops.exists(target):
            raise FileExistsError(target)
        self._atomic_write(target, content)
        self._logger.info("memory.create path=%s bytes=%d", path, len(content))

    def insert(self, path: PurePosixPath, after_line: int, content: str) -> None:
        target = self._resolve(path)
        existing = self._fops.read_text(target) if self._fops.exists(target) else ""
        lines = existing.splitlines(keepends=True)
        if after_line < 0 or after_line > len(lines):
            raise ValueError(f"Invalid after_line={after_line} for {len(lines)}-line file")
        block = content if content.endswith("\n") else content + "\n"
        new_text = "".join(lines[:after_line]) + block + "".join(lines[after_line:])
        self._atomic_write(target, new_text)
        self._logger.info(
            "memory.insert path=%s after_line=%d added=%d", path, after_line, len(block),
        )

    def str_replace(self, path: PurePosixPath, old: str, new: str) -> None:
        target = self._resolve(path)
        text = self._fops.read_text(target)
        if old not in text:
            raise KeyError(f"old string not found in {path}")
        if text.count(old) > 1:
            raise ValueError(f"old string is not unique in {path}")
        self._atomic_write(target, text.replace(old, new))
        self._logger.info("memory.str_replace path=%s", path)

    def delete(self, path: PurePosixPath) -> None:
        target = self._resolve(path)
        if not self._fops.exists(target):
            raise FileNotFoundError(target)
        if target.is_dir():
            self._fops.rmtree(target)
        else:
            self._fops.remove(target)
        self._logger.info("memory.delete path=%s", path)

    # ------------------------------------------------------------------
    # episodic + index helpers
    # ------------------------------------------------------------------
    def _today_path(self) -> Path:
        date_str = self._clock().strftime("%Y-%m-%d")
        return self._episodic_root / f"{date_str}.md"

    def append_episodic(self, entry: str) -> Path:
        target = self._today_path()
        existing = self._fops.read_text(target) if self._fops.exists(target) else ""
        suffix = entry if entry.endswith("\n") else entry + "\n"
        self._atomic_write(target, existing + suffix)
        self._logger.info("memory.episodic_append path=%s bytes=%d", target.name, len(suffix))
        return target

    def update_index(self, summary_line: str) -> None:
        existing = (
            self._fops.read_text(self.index_path)
            if self._fops.exists(self.index_path)
            else ""
        )
        line = summary_line if summary_line.endswith("\n") else summary_line + "\n"
        self._atomic_write(self.index_path, existing + line)
        self._logger.info("memory.index_append bytes=%d", len(line))

    def gc_heartbeat(self, iteration: int) -> bool:
        if iteration <= 0:
            return False
        if iteration % self._cfg.gc_heartbeat_iterations != 0:
            return False
        if not self._fops.exists(self.index_path):
            return False
        size = self._fops.stat_size(self.index_path)
        if size <= self._cfg.rotate_after_bytes:
            return False
        self.rotate_index()
        return True

    def rotate_index(self) -> Path:
        text = self._fops.read_text(self.index_path)
        encoded = text.encode("utf-8")
        keep_n = self._cfg.rotate_keep_tail_bytes
        archive_bytes = encoded[:-keep_n] if len(encoded) > keep_n else b""
        kept = encoded[-keep_n:].decode("utf-8", errors="replace") if archive_bytes else text
        timestamp = self._clock().strftime("%Y%m%dT%H%M%S")
        archive_path = self._root / f"{self._cfg.index_file}.{timestamp}.rotated.md"
        if archive_bytes:
            self._atomic_write(archive_path, archive_bytes.decode("utf-8", errors="replace"))
        self._atomic_write(self.index_path, kept)
        self._logger.info(
            "memory.rotate_index archive=%s kept_bytes=%d",
            archive_path.name,
            len(kept.encode("utf-8")),
        )
        return archive_path

    # ------------------------------------------------------------------
    # SPEC shard helpers
    # ------------------------------------------------------------------
    def write_spec_shard(
        self,
        slice_id: str,
        spec: str,
        task: str,
        learnings: str = "",
    ) -> Path:
        if not slice_id or "/" in slice_id or "\\" in slice_id:
            raise ValueError(f"Invalid slice_id: {slice_id!r}")
        shard_dir = self._spec_root / slice_id
        self._fops.mkdir(shard_dir, parents=True, exist_ok=True)
        self._atomic_write(shard_dir / "SPEC.md", spec if spec.endswith("\n") else spec + "\n")
        self._atomic_write(shard_dir / "task.md", task if task.endswith("\n") else task + "\n")
        learnings_text = learnings or "# Learnings\n"
        self._atomic_write(
            shard_dir / "learnings.md",
            learnings_text if learnings_text.endswith("\n") else learnings_text + "\n",
        )
        self._logger.info("memory.spec_shard slice=%s dir=%s", slice_id, shard_dir)
        return shard_dir
