"""Ingest pipeline: connects MultiTailer -> Normalizer -> RingBuffer."""

from __future__ import annotations

import asyncio
import logging

from .buffer import RingBuffer
from .normalizer import Normalizer
from .parsers import BaseParser, detect_format, get_parser
from .parsers.plain import PlainParser
from .tailer import MultiTailer

log = logging.getLogger(__name__)


class IngestPipeline:
    """Connects MultiTailer -> Normalizer -> RingBuffer."""

    def __init__(
        self,
        tailer: MultiTailer,
        buffer: RingBuffer,
        *,
        parser_overrides: dict[str, str] | None = None,
    ):
        self._tailer = tailer
        self._buffer = buffer
        self._parser_overrides = parser_overrides or {}

        # Lazily created normalizers keyed by (source, source_path)
        self._normalizers: dict[tuple[str, str], Normalizer] = {}

        # Samples collected per (source, source_path) for auto-detection
        self._samples: dict[tuple[str, str], list[str]] = {}
        self._sample_limit = 10

    def _get_parser(self, source: str, source_path: str, raw_line: str) -> BaseParser:
        """Resolve parser for a source. Uses explicit override, auto-detect, or plain fallback."""
        # Explicit parser override from config
        if source in self._parser_overrides:
            try:
                return get_parser(self._parser_overrides[source])
            except KeyError:
                log.warning(
                    "Unknown parser %r for source %r, falling back to plain",
                    self._parser_overrides[source],
                    source,
                )
                return PlainParser()

        # Auto-detect from collected samples
        key = (source, source_path)
        samples = self._samples.get(key, [])
        samples.append(raw_line)
        self._samples[key] = samples

        if len(samples) < self._sample_limit:
            # Not enough samples yet — use detect on what we have
            pass

        try:
            parser = detect_format(samples)
        except Exception:
            log.warning(
                "Parser detection failed for source=%r path=%r, falling back to plain",
                source,
                source_path,
            )
            parser = PlainParser()

        return parser

    def _get_normalizer(self, source: str, source_path: str, raw_line: str) -> Normalizer:
        """Get or create a normalizer for the given source+path combination."""
        key = (source, source_path)
        if key not in self._normalizers:
            parser = self._get_parser(source, source_path, raw_line)
            self._normalizers[key] = Normalizer(parser, source, source_path)
        return self._normalizers[key]

    async def run(self) -> None:
        """Main ingest loop. Runs until cancelled."""
        try:
            async for source, raw_line, source_path in self._tailer.stream():
                normalizer = self._get_normalizer(source, source_path, raw_line)
                event = normalizer.feed_line(raw_line)
                if event is not None:
                    self._buffer.append(event)
        except asyncio.CancelledError:
            # Flush all normalizers on shutdown
            for normalizer in self._normalizers.values():
                event = normalizer.flush()
                if event is not None:
                    self._buffer.append(event)
            raise

    def flush_all(self) -> None:
        """Flush all normalizers, pushing any buffered events to the ring buffer."""
        for normalizer in self._normalizers.values():
            event = normalizer.flush()
            if event is not None:
                self._buffer.append(event)


