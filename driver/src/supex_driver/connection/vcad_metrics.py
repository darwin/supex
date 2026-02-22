"""Centralized VCAD operational metrics registry.

Provides a single source of truth for all telemetry counters and gauges.
Metrics are collected from various driver components and exposed via the
vcad_metrics MCP tool as a stable JSON schema.

Counters are monotonic for one driver process lifetime.
Gauges represent current state and can move up/down.
"""

import threading
import time
from typing import Any


# Stable metric names (public contract, covered by tests)
METRIC_NAMES = [
    "queue_depth",
    "queue_rejected_total",
    "eval_timeout_total",
    "stale_dropped_total",
    "superseded_dropped_total",
    "superseded_skipped_before_eval_total",
    "coalesce_batches_total",
    "coalesce_merged_events_total",
    "coalesce_window_ms_effective",
    "artifact_manifests_written_total",
    "artifact_manifests_retained_current",
    "artifact_pair_recovery_total",
    "artifact_pair_incomplete_detected_total",
    "reconcile_runs_total",
    "reconcile_drift_total",
    "degraded_nodes_current",
    "viewer_reconnect_total",
]

COUNTER_METRICS = {
    "queue_rejected_total",
    "eval_timeout_total",
    "stale_dropped_total",
    "superseded_dropped_total",
    "superseded_skipped_before_eval_total",
    "coalesce_batches_total",
    "coalesce_merged_events_total",
    "artifact_manifests_written_total",
    "artifact_pair_recovery_total",
    "artifact_pair_incomplete_detected_total",
    "reconcile_runs_total",
    "reconcile_drift_total",
    "viewer_reconnect_total",
}

GAUGE_METRICS = {
    "queue_depth",
    "coalesce_window_ms_effective",
    "artifact_manifests_retained_current",
    "degraded_nodes_current",
}


class VcadMetrics:
    """Thread-safe centralized metrics registry.

    Some metrics are tracked directly via increment/set methods.
    Others are read from component state at snapshot time via
    registered gauge callbacks.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {name: 0 for name in COUNTER_METRICS}
        self._gauges: dict[str, float] = {name: 0.0 for name in GAUGE_METRICS}
        self._gauge_callbacks: dict[str, Any] = {}

    def increment(self, name: str, delta: int = 1) -> None:
        """Increment a counter metric.

        Args:
            name: Counter metric name (must be in COUNTER_METRICS).
            delta: Amount to increment (default 1).
        """
        with self._lock:
            if name in self._counters:
                self._counters[name] += delta

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric to a specific value.

        Args:
            name: Gauge metric name (must be in GAUGE_METRICS).
            value: New gauge value.
        """
        with self._lock:
            if name in self._gauges:
                self._gauges[name] = value

    def register_gauge_callback(self, name: str, callback: Any) -> None:
        """Register a callback to compute gauge value at snapshot time.

        The callback is invoked with no arguments and must return a numeric value.

        Args:
            name: Gauge metric name.
            callback: Callable returning current gauge value.
        """
        with self._lock:
            self._gauge_callbacks[name] = callback

    def get_counter(self, name: str) -> int:
        """Get current value of a counter."""
        with self._lock:
            return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        """Get current value of a gauge (evaluates callback if registered)."""
        with self._lock:
            if name in self._gauge_callbacks:
                try:
                    return float(self._gauge_callbacks[name]())
                except Exception:
                    return self._gauges.get(name, 0.0)
            return self._gauges.get(name, 0.0)

    def snapshot(self) -> dict[str, Any]:
        """Collect a full metrics snapshot.

        Returns:
            Dict with all metric values and collected_at timestamp.
        """
        with self._lock:
            result: dict[str, Any] = {}

            for name in COUNTER_METRICS:
                result[name] = self._counters.get(name, 0)

            for name in GAUGE_METRICS:
                if name in self._gauge_callbacks:
                    try:
                        result[name] = self._gauge_callbacks[name]()
                    except Exception:
                        result[name] = self._gauges.get(name, 0.0)
                else:
                    result[name] = self._gauges.get(name, 0.0)

            result["collected_at"] = time.time()

        return result

    def reset(self) -> None:
        """Reset all metrics to zero (for testing)."""
        with self._lock:
            for name in self._counters:
                self._counters[name] = 0
            for name in self._gauges:
                self._gauges[name] = 0.0


# Singleton
_metrics_lock = threading.Lock()
_metrics: VcadMetrics | None = None


def get_vcad_metrics() -> VcadMetrics:
    """Get or create the global VcadMetrics singleton."""
    global _metrics
    with _metrics_lock:
        if _metrics is None:
            _metrics = VcadMetrics()
        return _metrics


def _reset_vcad_metrics() -> None:
    """Reset the global metrics instance (for testing)."""
    global _metrics
    with _metrics_lock:
        _metrics = None
