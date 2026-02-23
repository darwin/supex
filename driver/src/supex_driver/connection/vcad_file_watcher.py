"""Filesystem watcher integration for VCAD nodes.

Polls the sidecar for file changes and triggers cascade updates
through the DAG when .cmp.oo source files change on disk.
"""

import logging
import os
import threading
from typing import Any

logger = logging.getLogger("supex.vcad.file_watcher")


class VCADFileWatcher:
    """Manages filesystem watching for VCAD source files.

    Communicates with the sidecar's notify-based watcher via JSON-RPC,
    polls for changes, and triggers DAG cascade updates.
    """

    def __init__(self) -> None:
        self._watch_dir: str | None = None
        self._lock = threading.Lock()

    @property
    def watch_dir(self) -> str | None:
        """The directory currently being watched, or None."""
        return self._watch_dir

    @property
    def is_watching(self) -> bool:
        """Whether the watcher is currently active."""
        return self._watch_dir is not None

    def start(self, dir: str, vcad_connection: Any) -> dict[str, Any]:
        """Start watching a project directory.

        Args:
            dir: Absolute path to the project directory.
            vcad_connection: VCADConnection instance to send commands through.

        Returns:
            Result dict from sidecar.
        """
        with self._lock:
            result = vcad_connection.watch_start(dir)
            self._watch_dir = dir
            logger.info(f"Started watching directory: {dir}")
            return dict(result)

    def stop(self, vcad_connection: Any) -> dict[str, Any]:
        """Stop watching.

        Args:
            vcad_connection: VCADConnection instance to send commands through.

        Returns:
            Result dict from sidecar.
        """
        with self._lock:
            result = vcad_connection.watch_stop()
            self._watch_dir = None
            logger.info("Stopped watching")
            return dict(result)

    def poll(self, vcad_connection: Any) -> list[dict[str, Any]]:
        """Poll for changed files since last poll.

        Args:
            vcad_connection: VCADConnection instance.

        Returns:
            List of change dicts with 'path' and 'kind'.
        """
        result = vcad_connection.watch_poll()
        return list(result.get("changes", []))

    def auto_start_if_needed(
        self, source_file: str, vcad_connection: Any
    ) -> None:
        """Auto-start watching if not already watching.

        Detects the project root from the source_file path and starts
        watching it. Called from vcad_place to enable automatic file watching.

        Args:
            source_file: Path to a .cmp.oo file being placed.
            vcad_connection: VCADConnection instance.
        """
        if self.is_watching:
            return

        project_root = _detect_project_root(source_file)
        if project_root:
            try:
                self.start(project_root, vcad_connection)
            except Exception as e:
                logger.warning(f"Failed to auto-start file watcher: {e}")

    def find_nodes_for_changes(
        self, changes: list[dict[str, Any]], dag: Any
    ) -> list[str]:
        """Find DAG node IDs whose source_file matches changed paths.

        Only matches vcad_loon changes (.cmp.oo files), not module library
        changes. For `.oo` library changes, use find_nodes_for_loon_changes().

        Args:
            changes: List of change dicts from poll().
            dag: VCADDag instance.

        Returns:
            List of node_ids whose source files changed.
        """
        changed_node_ids = []
        for change in changes:
            if change.get("kind") != "vcad_loon":
                continue
            changed_path = change.get("path", "")
            if not changed_path:
                continue
            # Normalize the path for comparison
            changed_abs = os.path.abspath(changed_path)
            for node_id, node in dag.nodes.items():
                node_abs = os.path.abspath(node.source_file)
                if node_abs == changed_abs:
                    changed_node_ids.append(node_id)
        return changed_node_ids

    def find_nodes_for_loon_changes(
        self,
        changes: list[dict[str, Any]],
        vcad_connection: Any,
    ) -> list[str]:
        """Find DAG node IDs affected by `.oo` library file changes.

        Queries the sidecar's module tracker for each changed `.oo` file
        to find nodes that depend on it via [use ...].

        Args:
            changes: List of change dicts from poll().
            vcad_connection: VCADConnection instance.

        Returns:
            Deduplicated list of node_ids affected by module changes.
        """
        affected_node_ids: set[str] = set()
        for change in changes:
            if change.get("kind") != "loon":
                continue
            changed_path = change.get("path", "")
            if not changed_path:
                continue
            try:
                node_ids = vcad_connection.get_affected_nodes(changed_path)
                affected_node_ids.update(node_ids)
            except Exception as e:
                logger.warning(
                    f"Failed to query affected nodes for {changed_path}: {e}"
                )
        return list(affected_node_ids)


def _detect_project_root(source_file: str) -> str | None:
    """Detect project root from a source file path.

    Walks up from the source file's directory looking for project markers:
    - A directory containing .cmp.oo files at the top level
    - Falls back to the source file's parent directory

    Args:
        source_file: Path to a .cmp.oo file.

    Returns:
        Absolute path to the project root, or None.
    """
    source_dir = os.path.dirname(os.path.abspath(source_file))
    if not os.path.isdir(source_dir):
        return None
    return source_dir


# Global singleton
_vcad_file_watcher: VCADFileWatcher | None = None
_vcad_file_watcher_lock = threading.Lock()


def get_vcad_file_watcher() -> VCADFileWatcher:
    """Get or create the global VCADFileWatcher singleton."""
    global _vcad_file_watcher
    with _vcad_file_watcher_lock:
        if _vcad_file_watcher is None:
            _vcad_file_watcher = VCADFileWatcher()
        return _vcad_file_watcher


def _reset_vcad_file_watcher() -> None:
    """Reset the global file watcher (for testing)."""
    global _vcad_file_watcher
    with _vcad_file_watcher_lock:
        _vcad_file_watcher = None
