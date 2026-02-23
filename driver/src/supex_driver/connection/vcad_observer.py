"""SketchUp model observer integration + unified reactive trigger flow.

Polls the Ruby bridge for entity changes (vcad.observer_poll), merges with
filesystem and module-tracker events, coalesces into batched cascades, and
supports pause/resume for agent batch operations.
"""

import logging
import os
import threading
import time
from typing import Any, Callable

from supex_driver.connection.vcad_state import TriggerCoalescer

logger = logging.getLogger("supex.vcad.observer")

# Environment variable defaults
VCAD_OBSERVER_POLL_MS = float(os.environ.get("SUPEX_VCAD_OBSERVER_POLL_MS", "250"))
VCAD_TRIGGER_COALESCE_MS = float(os.environ.get("SUPEX_VCAD_TRIGGER_COALESCE_MS", "150"))


class VCADObserverPoller:
    """Polls SketchUp bridge for entity changes via vcad.observer_poll.

    Runs a periodic background thread that calls vcad.observer_poll on the
    Ruby bridge. Changed entity IDs are looked up in the DAG to find affected
    vcad nodes, which are then fed into the trigger coalescer.
    """

    def __init__(
        self,
        poll_ms: float = VCAD_OBSERVER_POLL_MS,
    ) -> None:
        self.poll_ms = poll_ms
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._observer_started = False

    @property
    def is_polling(self) -> bool:
        """Whether the polling loop is currently active."""
        return self._running

    @property
    def observer_started(self) -> bool:
        """Whether the SketchUp observer has been started."""
        return self._observer_started

    def start_observer(self, sketchup_connection: Any) -> dict[str, Any]:
        """Attach the observer in SketchUp via vcad.observer_start.

        Args:
            sketchup_connection: SketchUpConnection instance.

        Returns:
            Result dict from the bridge.
        """
        result = sketchup_connection.send_command(
            method="vcad.observer_start",
            params={},
        )
        self._observer_started = True
        logger.info("SketchUp observer started")
        return result

    def stop_observer(self, sketchup_connection: Any) -> dict[str, Any]:
        """Detach the observer in SketchUp via vcad.observer_stop.

        Args:
            sketchup_connection: SketchUpConnection instance.

        Returns:
            Result dict from the bridge.
        """
        result = sketchup_connection.send_command(
            method="vcad.observer_stop",
            params={},
        )
        self._observer_started = False
        logger.info("SketchUp observer stopped")
        return result

    def poll_once(self, sketchup_connection: Any) -> dict[str, Any]:
        """Single poll: call vcad.observer_poll on the bridge.

        Returns:
            Dict with changed_entity_ids, dropped, queue_size.
        """
        return sketchup_connection.send_command(
            method="vcad.observer_poll",
            params={},
        )

    def start_polling(
        self,
        sketchup_connection: Any,
        on_entity_changes: Callable[[list[int]], None],
    ) -> None:
        """Start background polling loop.

        Args:
            sketchup_connection: SketchUpConnection instance.
            on_entity_changes: Callback invoked with list of changed entity IDs.
        """
        with self._lock:
            if self._running:
                return
            self._running = True

        def _poll_loop() -> None:
            interval = self.poll_ms / 1000.0
            while self._running:
                try:
                    result = self.poll_once(sketchup_connection)
                    changed = result.get("changed_entity_ids", [])
                    if changed:
                        on_entity_changes(changed)
                    dropped = result.get("dropped", 0)
                    if dropped > 0:
                        logger.warning(
                            f"Observer queue overflow: {dropped} events dropped"
                        )
                except Exception as e:
                    logger.debug(f"Observer poll error (will retry): {e}")
                time.sleep(interval)

        self._thread = threading.Thread(
            target=_poll_loop, daemon=True, name="vcad-observer-poll"
        )
        self._thread.start()
        logger.info(f"Observer polling started (interval={self.poll_ms}ms)")

    def stop_polling(self) -> None:
        """Stop the background polling loop."""
        with self._lock:
            self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Observer polling stopped")


class VCADReactiveWatcher:
    """Unified reactive watcher combining all change sources.

    Integrates:
    - SketchUp entity observer (poll-based via VCADObserverPoller)
    - Filesystem watcher (.cmp.oo files)
    - Module tracker (.oo library files)

    Supports pause/resume for agent batch operations. While paused,
    changes accumulate in a pending set but no cascades fire.
    """

    def __init__(
        self,
        coalesce_ms: float = VCAD_TRIGGER_COALESCE_MS,
    ) -> None:
        self._coalescer = TriggerCoalescer(
            coalesce_ms=coalesce_ms,
            callback=None,  # Set via set_cascade_callback
        )
        self._observer_poller = VCADObserverPoller()
        self._paused = False
        self._pending_while_paused: set[str] = set()
        self._lock = threading.Lock()
        self._reconciled = False

    @property
    def is_paused(self) -> bool:
        """Whether reactive watching is paused."""
        with self._lock:
            return self._paused

    @property
    def is_reconciled(self) -> bool:
        """Whether startup reconciliation has completed."""
        return self._reconciled

    @property
    def observer_poller(self) -> VCADObserverPoller:
        """Access to the underlying observer poller."""
        return self._observer_poller

    @property
    def coalescer(self) -> TriggerCoalescer:
        """Access to the underlying trigger coalescer."""
        return self._coalescer

    @property
    def pending_while_paused(self) -> set[str]:
        """Node IDs accumulated while paused (read-only copy)."""
        with self._lock:
            return self._pending_while_paused.copy()

    def mark_reconciled(self) -> None:
        """Mark that startup reconciliation is complete.

        The reactive loop should not fire cascades until reconciliation
        is done.
        """
        self._reconciled = True
        logger.info("Startup reconciliation complete, reactive loop enabled")

    def set_cascade_callback(
        self,
        callback: Callable[[set[str]], None],
    ) -> None:
        """Set the callback that executes topological cascade.

        Args:
            callback: Function called with set of affected node_ids.
        """
        self._coalescer.callback = callback

    def trigger(self, node_id: str, source: str = "") -> None:
        """Register a change event for a node.

        If paused, accumulates in pending set. If not reconciled yet, ignores.
        Otherwise feeds into the trigger coalescer.

        Args:
            node_id: The affected node identifier.
            source: Event source label (fs-watch, mod-track, su-observer, manual).
        """
        if not self._reconciled:
            logger.debug(
                f"Ignoring trigger for {node_id} (not reconciled yet)"
            )
            return

        with self._lock:
            if self._paused:
                self._pending_while_paused.add(node_id)
                logger.debug(
                    f"Paused: accumulated {node_id} from {source}"
                )
                return

        self._coalescer.trigger(node_id, source)

    def trigger_many(self, node_ids: list[str], source: str = "") -> None:
        """Register change events for multiple nodes.

        Args:
            node_ids: List of affected node identifiers.
            source: Event source label.
        """
        for nid in node_ids:
            self.trigger(nid, source)

    def pause(self) -> dict[str, Any]:
        """Pause reactive watching.

        Changes accumulate but no cascades fire.

        Returns:
            Status dict.
        """
        with self._lock:
            if self._paused:
                return {
                    "success": True,
                    "status": "already_paused",
                    "pending_count": len(self._pending_while_paused),
                }
            self._paused = True
            self._pending_while_paused.clear()

        self._coalescer.cancel()
        logger.info("Reactive watching paused")
        return {"success": True, "status": "paused"}

    def resume(self) -> dict[str, Any]:
        """Resume reactive watching and flush accumulated changes.

        All pending node IDs are merged, deduplicated, and triggered
        as a single coalesced cascade.

        Returns:
            Status dict with flushed node count.
        """
        with self._lock:
            if not self._paused:
                return {
                    "success": True,
                    "status": "already_running",
                    "flushed": 0,
                }
            self._paused = False
            pending = self._pending_while_paused.copy()
            self._pending_while_paused.clear()

        flushed = len(pending)
        if pending:
            for nid in pending:
                self._coalescer.trigger(nid, "resume-flush")
            logger.info(f"Resumed: flushing {flushed} accumulated node(s)")
        else:
            logger.info("Resumed: no pending changes")

        return {"success": True, "status": "resumed", "flushed": flushed}

    def stop(self) -> None:
        """Stop all watching (poller + coalescer)."""
        self._observer_poller.stop_polling()
        self._coalescer.cancel()
        with self._lock:
            self._paused = False
            self._pending_while_paused.clear()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_vcad_reactive_watcher: VCADReactiveWatcher | None = None
_vcad_reactive_watcher_lock = threading.Lock()


def get_vcad_reactive_watcher() -> VCADReactiveWatcher:
    """Get or create the global VCADReactiveWatcher singleton."""
    global _vcad_reactive_watcher
    with _vcad_reactive_watcher_lock:
        if _vcad_reactive_watcher is None:
            _vcad_reactive_watcher = VCADReactiveWatcher()
        return _vcad_reactive_watcher


def _reset_vcad_reactive_watcher() -> None:
    """Reset the global reactive watcher (for testing)."""
    global _vcad_reactive_watcher
    with _vcad_reactive_watcher_lock:
        if _vcad_reactive_watcher is not None:
            _vcad_reactive_watcher.stop()
        _vcad_reactive_watcher = None
