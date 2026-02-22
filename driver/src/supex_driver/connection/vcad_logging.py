"""Structured logging and correlation ID management for VCAD observability.

Provides:
- Thread-local correlation ID (request_id) management
- Structured JSON event emitter with required fields
- Required event name constants

Every MCP vcad request carries a request_id (correlation_id) from tool entry
through driver logs, sidecar JSON-RPC metadata, SketchUp bridge calls, and
viewer relay messages/events.
"""

import json
import logging
import threading
import time
import uuid
from typing import Any

logger = logging.getLogger("supex.vcad.telemetry")

# Required event names (public contract)
EVENT_EVAL_ENQUEUED = "eval_enqueued"
EVENT_EVAL_STARTED = "eval_started"
EVENT_EVAL_FINISHED = "eval_finished"
EVENT_EVAL_TIMEOUT = "eval_timeout"
EVENT_STALE_DROPPED = "stale_dropped"
EVENT_RECONCILE_STARTED = "reconcile_started"
EVENT_RECONCILE_FINISHED = "reconcile_finished"
EVENT_VIEWER_RECONNECTED = "viewer_reconnected"

REQUIRED_EVENTS = [
    EVENT_EVAL_ENQUEUED,
    EVENT_EVAL_STARTED,
    EVENT_EVAL_FINISHED,
    EVENT_EVAL_TIMEOUT,
    EVENT_STALE_DROPPED,
    EVENT_RECONCILE_STARTED,
    EVENT_RECONCILE_FINISHED,
    EVENT_VIEWER_RECONNECTED,
]


# Thread-local storage for correlation ID
_correlation = threading.local()


def set_correlation_id(request_id: str | None = None) -> str:
    """Set the correlation ID for the current thread.

    Args:
        request_id: Explicit ID to use, or None to auto-generate.

    Returns:
        The correlation ID that was set.
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    _correlation.request_id = request_id
    return request_id


def get_correlation_id() -> str | None:
    """Get the current thread's correlation ID, or None if not set."""
    return getattr(_correlation, "request_id", None)


def clear_correlation_id() -> None:
    """Clear the current thread's correlation ID."""
    _correlation.request_id = None


def emit_event(
    event: str,
    *,
    level: str = "INFO",
    request_id: str | None = None,
    node_id: str | None = None,
    error_code: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Emit a structured log event with required fields.

    Structured log events (JSON) include at least:
    - timestamp, level, request_id, node_id (when available),
      event, error_code (when failure)

    Args:
        event: Event name (e.g. eval_enqueued, eval_finished).
        level: Log level string (INFO, WARNING, ERROR, DEBUG).
        request_id: Explicit correlation ID (falls back to thread-local).
        node_id: VCAD node identifier (when available).
        error_code: Error code string (when failure).
        **extra: Additional fields to include in the event.

    Returns:
        The structured event dict (also logged via logger).
    """
    if request_id is None:
        request_id = get_correlation_id()

    record: dict[str, Any] = {
        "timestamp": time.time(),
        "level": level,
        "request_id": request_id,
        "node_id": node_id,
        "event": event,
    }

    if error_code is not None:
        record["error_code"] = error_code

    record.update(extra)

    # Log the structured event as JSON
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, json.dumps(record))

    return record
