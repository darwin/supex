"""File watch/tail layer with rotate and truncate detection."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class TailSource:
    """Descriptor for a file to tail."""

    source: str  # logical source ID from config
    source_path: Path


class FileTailer:
    """Watches one file for new content. Handles rotate and truncate."""

    def __init__(self, path: Path, poll_interval: float = 0.2):
        self.path = path
        self.poll_interval = poll_interval
        self.offset: int = 0
        self.inode: int | None = None

    async def read_new_lines(self) -> list[str]:
        """Return new lines since last read. Detect rotate/truncate."""
        try:
            stat = os.stat(self.path)
        except FileNotFoundError:
            log.warning("File not found: %s", self.path)
            self.inode = None
            self.offset = 0
            return []

        current_inode = stat.st_ino

        if self._detect_rotate(current_inode):
            log.info("Rotate detected: %s (inode %s -> %s)", self.path, self.inode, current_inode)
            self.inode = current_inode
            self.offset = 0
        elif self._detect_truncate(stat.st_size):
            log.info("Truncate detected: %s (size %d < offset %d)", self.path, stat.st_size, self.offset)
            self.offset = 0

        if self.inode is None:
            self.inode = current_inode

        if stat.st_size <= self.offset:
            return []

        try:
            with open(self.path, "r", errors="replace") as f:
                f.seek(self.offset)
                data = f.read()
                self.offset = f.tell()
        except (OSError, ValueError) as exc:
            log.warning("Error reading %s: %s", self.path, exc)
            return []

        if not data:
            return []

        lines = data.splitlines()
        # If data ends without newline, the last line is incomplete — hold it back
        if not data.endswith("\n"):
            self.offset -= len(data.split("\n")[-1].encode())
            lines = lines[:-1]

        return lines

    def _detect_rotate(self, current_inode: int) -> bool:
        """Inode changed -> rotated."""
        return self.inode is not None and current_inode != self.inode

    def _detect_truncate(self, current_size: int) -> bool:
        """Same inode but size < offset -> truncated."""
        return self.inode is not None and current_size < self.offset


class MultiTailer:
    """Manages multiple FileTailers, yields (source, line, source_path) tuples."""

    def __init__(self, sources: list[TailSource], poll_interval: float = 0.2):
        self.poll_interval = poll_interval
        self.tailers: list[tuple[TailSource, FileTailer]] = [
            (src, FileTailer(src.source_path, poll_interval=poll_interval))
            for src in sources
        ]

    async def stream(self) -> AsyncIterator[tuple[str, str, str]]:
        """Infinite async generator of (source_id, raw_line, source_path)."""
        while True:
            had_output = False
            for src, tailer in self.tailers:
                lines = await tailer.read_new_lines()
                for line in lines:
                    had_output = True
                    yield (src.source, line, str(src.source_path))
            if not had_output:
                await asyncio.sleep(self.poll_interval)
