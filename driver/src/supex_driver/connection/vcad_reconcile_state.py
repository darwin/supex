"""Reconciliation state tracker for observability.

Records the result of the most recent reconciliation run for exposure
via the vcad_reconcile_status MCP tool.
"""

import threading
import time
from typing import Any


class ReconcileState:
    """Tracks the most recent reconciliation run result."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_run_at: float | None = None
        self._drift: dict[str, list[str]] = {}
        self._pending_nodes: list[str] = []
        self._last_outcome: str = "none"

    def record_run(
        self,
        drift: dict[str, list[str]],
        pending_nodes: list[str] | None = None,
        outcome: str = "ok",
    ) -> None:
        """Record the result of a reconciliation run.

        Args:
            drift: Drift buckets (missing_node, orphan_definition, etc.).
            pending_nodes: Nodes still requiring corrective action.
            outcome: Overall outcome (ok, reconciled, degraded).
        """
        with self._lock:
            self._last_run_at = time.time()
            self._drift = dict(drift)
            self._pending_nodes = list(pending_nodes or [])
            self._last_outcome = outcome

    def snapshot(self) -> dict[str, Any]:
        """Get the current reconcile state as a dict.

        Returns:
            Dict with last_run_at, drift, pending_nodes, last_outcome.
        """
        with self._lock:
            return {
                "last_run_at": self._last_run_at,
                "drift": dict(self._drift),
                "pending_nodes": list(self._pending_nodes),
                "last_outcome": self._last_outcome,
            }


# Singleton
_reconcile_state_lock = threading.Lock()
_reconcile_state: ReconcileState | None = None


def get_reconcile_state() -> ReconcileState:
    """Get or create the global ReconcileState singleton."""
    global _reconcile_state
    with _reconcile_state_lock:
        if _reconcile_state is None:
            _reconcile_state = ReconcileState()
        return _reconcile_state


def _reset_reconcile_state() -> None:
    """Reset the global reconcile state (for testing)."""
    global _reconcile_state
    with _reconcile_state_lock:
        _reconcile_state = None
