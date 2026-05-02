"""Hash-anchored file edits.

Every line is tagged with a content hash so the model can dictate edits by
referencing stable identifiers; if the file has mutated under us, hashes
mismatch and the edit aborts before corruption occurs.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import EditsConfig
from .logging_ext import get_runtime_logger


@dataclass(frozen=True)
class AnchoredLine:
    line_no: int
    digest: str
    text: str


class HashMismatchError(RuntimeError):
    """Raised when a stored anchor digest does not match the live file content."""


class FileOps(Protocol):
    def read_text(self, path: Path) -> str: ...
    def write_text(self, path: Path, content: str) -> None: ...


@dataclass(frozen=True)
class _RealFileOps:
    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _default_hasher(algo: str, prefix_length: int) -> Callable[[bytes], str]:
    def _hash(data: bytes) -> str:
        digest = hashlib.new(algo)
        digest.update(data)
        return digest.hexdigest()[:prefix_length]

    return _hash


class HashAnchoredEditor:
    def __init__(
        self,
        cfg: EditsConfig,
        *,
        hasher: Callable[[bytes], str] | None = None,
        file_ops: FileOps | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._hasher = hasher or _default_hasher(cfg.hash_algo, cfg.hash_prefix_length)
        self._fops: FileOps = file_ops or _RealFileOps()
        self._logger = logger or get_runtime_logger("edits")

    def annotate(self, text: str) -> list[AnchoredLine]:
        normalized = _normalize(text)
        lines = normalized.split("\n")
        anchored: list[AnchoredLine] = []
        for index, line in enumerate(lines, start=1):
            anchored.append(
                AnchoredLine(
                    line_no=index,
                    digest=self._hasher(line.encode("utf-8")),
                    text=line,
                )
            )
        return anchored

    def render(self, lines: Sequence[AnchoredLine]) -> str:
        return "\n".join(line.text for line in lines)

    def apply_edit(
        self,
        path: Path,
        *,
        expected: Sequence[AnchoredLine],
        replacement: Sequence[AnchoredLine],
    ) -> None:
        live_text = self._fops.read_text(path)
        live_lines = self.annotate(live_text)
        mismatches: list[tuple[int, str, str]] = []
        live_by_no = {line.line_no: line for line in live_lines}
        for exp in expected:
            actual = live_by_no.get(exp.line_no)
            if actual is None or actual.digest != exp.digest:
                mismatches.append((exp.line_no, exp.digest, actual.digest if actual else ""))
        if mismatches:
            self._logger.error(
                "edits.hash_mismatch path=%s count=%d first=%s",
                path, len(mismatches), mismatches[0],
            )
            if self._cfg.mismatch_behavior == "abort":
                raise HashMismatchError(
                    f"hash mismatch in {path}: {len(mismatches)} line(s) drifted"
                )
            self._logger.warning("edits.hash_mismatch_warn path=%s", path)
        new_text = self.render(replacement)
        if new_text and not new_text.endswith("\n"):
            new_text += "\n"
        self._fops.write_text(path, new_text)
        self._logger.info(
            "edits.apply path=%s lines=%d", path, len(replacement),
        )
