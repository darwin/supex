"""VCAD dependency graph (DAG) for tracking node relationships.

Tracks edges between vcad nodes (entity imports, vcad-to-vcad solid imports)
and provides topological ordering for cascading re-evaluation.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from supex_driver.connection.vcad_state import (
    NodeState,
    RevisionTracker,
    VCADPersistentState,
    VCADReconciler,
)

logger = logging.getLogger("supex.vcad.dag")


@dataclass
class ImportRef:
    """A single import reference from a vcad node."""

    binding_name: str  # Loon var name
    selector: str  # "entity:12345" (for :host source)
    source: str = "host"  # source keyword
    extracts: list[str] = field(default_factory=list)  # [] = all, ["solid"], ["dims", "bbox"]
    resolved_type: str = "native"  # "native", "vcad", or "native_mesh"
    source_node_id: str | None = None  # set if resolved_type == "vcad"


@dataclass
class VCADNode:
    """A node in the vcad dependency graph."""

    node_id: str
    source_file: str
    imports: list[ImportRef] = field(default_factory=list)
    revision: int = 0
    applied_revision: int = 0
    last_entity_id: str | None = None
    status: str = "active"  # active | degraded | orphan


class VCADDag:
    """Dependency graph tracking vcad node relationships.

    Manages the in-memory graph of VCADNode objects and delegates
    persistence to VCADPersistentState and revision tracking to
    RevisionTracker from vcad_state.py.
    """

    def __init__(
        self,
        state: VCADPersistentState | None = None,
        tracker: RevisionTracker | None = None,
    ):
        self.nodes: dict[str, VCADNode] = {}
        self.state = state or VCADPersistentState()
        self.tracker = tracker or RevisionTracker()

    def add_node(self, node: VCADNode) -> None:
        """Add or replace a node in the DAG."""
        self.nodes[node.node_id] = node
        self.tracker.set_revision(node.node_id, node.revision)
        self._sync_to_state(node)

    def remove_node(self, node_id: str) -> None:
        """Remove a node from the DAG."""
        self.nodes.pop(node_id, None)
        self.tracker.remove_node(node_id)
        self.state.remove_node(node_id)

    def get_node(self, node_id: str) -> VCADNode | None:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_evaluation_order(self) -> list[str]:
        """Topological sort of all nodes.

        Returns node IDs in dependency order (dependencies first).
        Raises ValueError if a cycle is detected.
        """
        return self._topological_sort(list(self.nodes.keys()))

    def get_downstream(self, node_id: str) -> list[str]:
        """All nodes that depend (transitively) on node_id.

        Returns list of node IDs excluding the input node_id itself.
        """
        dependents: set[str] = set()
        queue: deque[str] = deque([node_id])

        while queue:
            current = queue.popleft()
            for nid, node in self.nodes.items():
                if nid in dependents or nid == node_id:
                    continue
                for imp in node.imports:
                    if imp.source_node_id == current:
                        dependents.add(nid)
                        queue.append(nid)
                        break

        return list(dependents)

    def get_dependents_of_entity(self, entity_id: str) -> list[str]:
        """All nodes that import this SketchUp entity (native or vcad-backed)."""
        result = []
        entity_ref = f"entity:{entity_id}"
        for nid, node in self.nodes.items():
            for imp in node.imports:
                if imp.selector == entity_ref:
                    result.append(nid)
                    break
        return result

    def bump_revision(self, node_id: str) -> int:
        """Increment and return next expected revision for node_id."""
        rev = self.tracker.next_revision(node_id)
        node = self.nodes.get(node_id)
        if node:
            node.revision = rev
        return rev

    def current_revision(self, node_id: str) -> int:
        """Get current revision for a node."""
        return self.tracker.current_revision(node_id)

    def should_apply(self, node_id: str, revision: int) -> bool:
        """Check if a result should be applied (not stale)."""
        return self.tracker.should_apply(node_id, revision)

    def mark_applied(self, node_id: str, revision: int) -> None:
        """Mark a revision as successfully applied."""
        node = self.nodes.get(node_id)
        if node:
            node.applied_revision = revision
            self._sync_to_state(node)

    def load_persisted_state(self) -> None:
        """Load persisted state and reconstruct DAG nodes."""
        if not self.state.load():
            return

        for nid, ns in self.state.all_nodes().items():
            if nid not in self.nodes:
                self.nodes[nid] = VCADNode(
                    node_id=ns.node_id,
                    source_file=ns.source_file,
                    revision=ns.revision,
                    applied_revision=ns.applied_revision,
                    last_entity_id=ns.last_entity_id,
                    status=ns.status,
                )

        VCADReconciler.rebuild_revisions(self.state, self.tracker)

    def persist_state(self) -> None:
        """Persist current DAG state to disk."""
        for node in self.nodes.values():
            self._sync_to_state(node)
        self.state.save()

    def reconcile_with_sketchup(
        self, sketchup_nodes: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """Reconcile DAG state with SketchUp runtime state.

        Returns dict with drift buckets:
        - missing_node: persisted but absent in SketchUp
        - orphan_definition: in SketchUp but not persisted
        - revision_gap: applied_revision behind revision
        - source_missing: source file not found on disk
        """
        from supex_driver.connection.vcad_metrics import get_vcad_metrics
        from supex_driver.connection.vcad_reconcile_state import get_reconcile_state

        metrics = get_vcad_metrics()
        metrics.increment("reconcile_runs_total")

        persisted = self.state.all_nodes()
        drift = VCADReconciler.classify_drift(persisted, sketchup_nodes)
        VCADReconciler.reconcile(self.state, drift)

        # Track total drift items
        metrics.increment("reconcile_drift_total", len(drift))

        # Update in-memory DAG from reconciled state
        for ns in self.state.all_nodes().values():
            if ns.node_id in self.nodes:
                self.nodes[ns.node_id].status = ns.status
            else:
                self.nodes[ns.node_id] = VCADNode(
                    node_id=ns.node_id,
                    source_file=ns.source_file,
                    revision=ns.revision,
                    applied_revision=ns.applied_revision,
                    last_entity_id=ns.last_entity_id,
                    status=ns.status,
                )

        # Remove nodes that were removed from persisted state
        current_persisted = set(self.state.all_nodes().keys())
        for nid in list(self.nodes.keys()):
            if nid not in current_persisted and nid not in {
                n["node_id"] for n in sketchup_nodes
            }:
                self.nodes.pop(nid, None)
                self.tracker.remove_node(nid)

        # Rebuild revision tracker from reconciled state
        VCADReconciler.rebuild_revisions(self.state, self.tracker)

        # Classify into buckets for the caller
        buckets: dict[str, list[str]] = {
            "missing_node": [],
            "orphan_definition": [],
            "revision_gap": [],
            "source_missing": [],
        }
        for d in drift:
            buckets.setdefault(d.drift_type, []).append(d.node_id)

        self.persist_state()

        # Update degraded_nodes_current gauge
        degraded_count = sum(
            1 for n in self.nodes.values() if n.status == "degraded"
        )
        metrics.set_gauge("degraded_nodes_current", float(degraded_count))

        # Record reconcile result for diagnostics
        pending_nodes = buckets.get("revision_gap", [])
        outcome = "degraded" if buckets.get("source_missing") else "ok"
        if any(v for v in buckets.values()):
            outcome = "reconciled" if outcome == "ok" else outcome
        reconcile_state = get_reconcile_state()
        reconcile_state.record_run(
            drift=buckets,
            pending_nodes=pending_nodes,
            outcome=outcome,
        )

        return buckets

    def detect_cycle(self) -> list[str] | None:
        """Detect a cycle in the DAG.

        Returns a list of node IDs forming the cycle, or None if acyclic.
        """
        # Build adjacency: source_node_id -> dependent_node_id
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def _dfs(node_id: str) -> list[str] | None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            # Find nodes that depend on this node
            for nid, node in self.nodes.items():
                for imp in node.imports:
                    if imp.source_node_id == node_id:
                        if nid not in visited:
                            result = _dfs(nid)
                            if result is not None:
                                return result
                        elif nid in rec_stack:
                            # Found cycle
                            cycle_start = path.index(nid)
                            return path[cycle_start:] + [nid]

            path.pop()
            rec_stack.discard(node_id)
            return None

        for nid in self.nodes:
            if nid not in visited:
                cycle = _dfs(nid)
                if cycle is not None:
                    return cycle

        return None

    def _topological_sort(self, node_ids: list[str]) -> list[str]:
        """Topological sort of a subset of nodes.

        Returns nodes in dependency order (dependencies first).
        """
        subset = set(node_ids)

        # Build in-degree map for subset: count how many subset-nodes
        # each node depends on
        in_degree: dict[str, int] = dict.fromkeys(subset, 0)
        # adjacency: source -> list of dependents
        adj: dict[str, list[str]] = {nid: [] for nid in subset}

        for nid in subset:
            node = self.nodes.get(nid)
            if not node:
                continue
            for imp in node.imports:
                src = imp.source_node_id
                if src and src in subset:
                    in_degree[nid] += 1
                    adj[src].append(nid)

        queue: deque[str] = deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )
        result: list[str] = []

        while queue:
            current = queue.popleft()
            result.append(current)
            for dependent in adj.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(subset):
            logger.warning(
                "Cycle detected in DAG subset — returning partial order"
            )

        return result

    def _sync_to_state(self, node: VCADNode) -> None:
        """Sync a VCADNode to the persistent state store."""
        self.state.set_node(
            NodeState(
                node_id=node.node_id,
                source_file=node.source_file,
                revision=node.revision,
                applied_revision=node.applied_revision,
                last_entity_id=node.last_entity_id,
                status=node.status,
            )
        )
