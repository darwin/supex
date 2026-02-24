"""Parser registry, base class, and format auto-detection."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParsedRecord:
    """Intermediate parsed result before normalization into LogEvent."""

    timestamp: datetime | None
    level: str | None
    message: str
    structured: dict | None


class BaseParser(ABC):
    """Abstract base for log format parsers."""

    @abstractmethod
    def parse_line(self, raw: str) -> ParsedRecord | None:
        """Parse a single line. Return None if not recognized."""

    def is_continuation(self, line: str) -> bool:
        """Return True if line is a continuation of previous record (multiline)."""
        return False


# Registry: name -> parser class
_PARSER_REGISTRY: dict[str, type[BaseParser]] = {}


def register_parser(name: str, cls: type[BaseParser]) -> None:
    """Register a parser class under a name."""
    _PARSER_REGISTRY[name] = cls


def get_parser(name: str) -> BaseParser:
    """Instantiate a parser by registered name."""
    if name not in _PARSER_REGISTRY:
        raise KeyError(f"Unknown parser: {name!r}")
    return _PARSER_REGISTRY[name]()


def detect_format(sample_lines: list[str]) -> BaseParser:
    """Auto-detect log format from first N lines.

    Tries JSONL first (lines starting with '{'), then pipe-separated
    (lines with '|' delimiters), falls back to plain text.
    """
    from .jsonl import JsonlParser
    from .pipe import PipeParser
    from .plain import PlainParser

    if not sample_lines:
        return PlainParser()

    jsonl_score = 0
    pipe_score = 0

    for line in sample_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("{"):
            jsonl_score += 1
        elif stripped.count("|") >= 2:
            pipe_score += 1

    total = len([ln for ln in sample_lines if ln.strip()])
    if total == 0:
        return PlainParser()

    if jsonl_score > total / 2:
        return JsonlParser()
    if pipe_score > total / 2:
        return PipeParser()
    return PlainParser()


# Import submodules to trigger registration
from . import jsonl as _jsonl, pipe as _pipe, plain as _plain  # noqa: E402, F401
