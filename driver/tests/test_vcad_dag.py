"""Tests for VCAD dependency graph (DAG)."""

import json
import os
import tempfile

import pytest

from supex_driver.connection.vcad_dag import ImportRef, VCADDag, VCADNode
from supex_driver.connection.vcad_state import (
    RevisionTracker,
    VCADPersistentState,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_state_path(tmp_path):
    """Temporary path for persistent state file."""
    return str(tmp_path / "vcad-state.json")


@pytest.fixture
def dag(tmp_state_path):
    """Create a fresh VCADDag with temporary state path."""
    state = VCADPersistentState(state_path=tmp_state_path)
    tracker = RevisionTracker()
    return VCADDag(state=state, tracker=tracker)


# ---------------------------------------------------------------------------
# Basic node management
# ---------------------------------------------------------------------------


class TestVCADDagBasic:
    """Test basic DAG node operations."""

    def test_add_node(self, dag: VCADDag) -> None:
        node = VCADNode(node_id="node-1", source_file="/test/a.cmp.oo")
        dag.add_node(node)

        assert "node-1" in dag.nodes
        assert dag.get_node("node-1") is node

    def test_remove_node(self, dag: VCADDag) -> None:
        dag.add_node(VCADNode(node_id="node-1", source_file="/test/a.cmp.oo"))
        dag.add_node(VCADNode(node_id="node-2", source_file="/test/b.cmp.oo"))

        dag.remove_node("node-1")

        assert "node-1" not in dag.nodes
        assert "node-2" in dag.nodes

    def test_remove_nonexistent_node(self, dag: VCADDag) -> None:
        dag.remove_node("nonexistent")  # Should not raise

    def test_get_nonexistent_node(self, dag: VCADDag) -> None:
        assert dag.get_node("nonexistent") is None

    def test_add_node_replaces_existing(self, dag: VCADDag) -> None:
        dag.add_node(VCADNode(
            node_id="node-1", source_file="/test/old.cmp.oo"
        ))
        dag.add_node(VCADNode(
            node_id="node-1", source_file="/test/new.cmp.oo"
        ))

        assert dag.get_node("node-1").source_file == "/test/new.cmp.oo"


# ---------------------------------------------------------------------------
# Dependency tracking
# ---------------------------------------------------------------------------


class TestVCADDagDependencies:
    """Test dependency tracking and downstream computation."""

    def _make_dag_with_chain(self, dag: VCADDag) -> None:
        """Create A -> B -> C chain (C depends on B depends on A)."""
        dag.add_node(VCADNode(node_id="A", source_file="/test/a.cmp.oo"))
        dag.add_node(VCADNode(
            node_id="B",
            source_file="/test/b.cmp.oo",
            imports=[ImportRef(
                binding_name="a_solid",
                selector="entity:100",
                extracts=["solid"],
                resolved_type="vcad",
                source_node_id="A",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="C",
            source_file="/test/c.cmp.oo",
            imports=[ImportRef(
                binding_name="b_solid",
                selector="entity:200",
                extracts=["solid"],
                resolved_type="vcad",
                source_node_id="B",
            )],
        ))

    def test_get_downstream_chain(self, dag: VCADDag) -> None:
        """A -> B -> C: downstream of A is [B, C]."""
        self._make_dag_with_chain(dag)

        downstream = dag.get_downstream("A")
        assert set(downstream) == {"B", "C"}

    def test_get_downstream_middle(self, dag: VCADDag) -> None:
        """A -> B -> C: downstream of B is [C]."""
        self._make_dag_with_chain(dag)

        downstream = dag.get_downstream("B")
        assert downstream == ["C"]

    def test_get_downstream_leaf(self, dag: VCADDag) -> None:
        """A -> B -> C: downstream of C is []."""
        self._make_dag_with_chain(dag)

        downstream = dag.get_downstream("C")
        assert downstream == []

    def test_get_downstream_nonexistent(self, dag: VCADDag) -> None:
        downstream = dag.get_downstream("nonexistent")
        assert downstream == []

    def test_get_dependents_of_entity(self, dag: VCADDag) -> None:
        dag.add_node(VCADNode(
            node_id="node-1",
            source_file="/test/a.cmp.oo",
            imports=[ImportRef(
                binding_name="dims",
                selector="entity:42",
                extracts=["dims"],
                resolved_type="native",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="node-2",
            source_file="/test/b.cmp.oo",
            imports=[ImportRef(
                binding_name="bbox",
                selector="entity:42",
                extracts=["bbox"],
                resolved_type="native",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="node-3",
            source_file="/test/c.cmp.oo",
            imports=[ImportRef(
                binding_name="dims",
                selector="entity:99",
                extracts=["dims"],
                resolved_type="native",
            )],
        ))

        dependents = dag.get_dependents_of_entity("42")
        assert set(dependents) == {"node-1", "node-2"}

    def test_diamond_dependency(self, dag: VCADDag) -> None:
        """Diamond: A -> B, A -> C, B -> D, C -> D.
        Downstream of A should include B, C, D.
        """
        dag.add_node(VCADNode(node_id="A", source_file="/test/a.cmp.oo"))
        dag.add_node(VCADNode(
            node_id="B",
            source_file="/test/b.cmp.oo",
            imports=[ImportRef(
                binding_name="a", selector="entity:1",
                extracts=["solid"], resolved_type="vcad", source_node_id="A",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="C",
            source_file="/test/c.cmp.oo",
            imports=[ImportRef(
                binding_name="a", selector="entity:1",
                extracts=["solid"], resolved_type="vcad", source_node_id="A",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="D",
            source_file="/test/d.cmp.oo",
            imports=[
                ImportRef(
                    binding_name="b", selector="entity:2",
                    extracts=["solid"], resolved_type="vcad", source_node_id="B",
                ),
                ImportRef(
                    binding_name="c", selector="entity:3",
                    extracts=["solid"], resolved_type="vcad", source_node_id="C",
                ),
            ],
        ))

        downstream = dag.get_downstream("A")
        assert set(downstream) == {"B", "C", "D"}


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------


class TestVCADDagTopologicalSort:
    """Test topological ordering of nodes."""

    def test_linear_chain(self, dag: VCADDag) -> None:
        """A -> B -> C should sort as [A, B, C]."""
        dag.add_node(VCADNode(node_id="A", source_file="/a.cmp.oo"))
        dag.add_node(VCADNode(
            node_id="B", source_file="/b.cmp.oo",
            imports=[ImportRef(
                binding_name="a", selector="entity:1",
                extracts=["solid"], resolved_type="vcad", source_node_id="A",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="C", source_file="/c.cmp.oo",
            imports=[ImportRef(
                binding_name="b", selector="entity:2",
                extracts=["solid"], resolved_type="vcad", source_node_id="B",
            )],
        ))

        order = dag.get_evaluation_order()
        assert order.index("A") < order.index("B") < order.index("C")

    def test_diamond(self, dag: VCADDag) -> None:
        """Diamond: A before B,C before D."""
        dag.add_node(VCADNode(node_id="A", source_file="/a.cmp.oo"))
        dag.add_node(VCADNode(
            node_id="B", source_file="/b.cmp.oo",
            imports=[ImportRef(
                binding_name="a", selector="entity:1",
                extracts=["solid"], resolved_type="vcad", source_node_id="A",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="C", source_file="/c.cmp.oo",
            imports=[ImportRef(
                binding_name="a", selector="entity:1",
                extracts=["solid"], resolved_type="vcad", source_node_id="A",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="D", source_file="/d.cmp.oo",
            imports=[
                ImportRef(
                    binding_name="b", selector="entity:2",
                    extracts=["solid"], resolved_type="vcad", source_node_id="B",
                ),
                ImportRef(
                    binding_name="c", selector="entity:3",
                    extracts=["solid"], resolved_type="vcad", source_node_id="C",
                ),
            ],
        ))

        order = dag.get_evaluation_order()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_independent_nodes(self, dag: VCADDag) -> None:
        """Independent nodes can appear in any order."""
        dag.add_node(VCADNode(node_id="X", source_file="/x.cmp.oo"))
        dag.add_node(VCADNode(node_id="Y", source_file="/y.cmp.oo"))
        dag.add_node(VCADNode(node_id="Z", source_file="/z.cmp.oo"))

        order = dag.get_evaluation_order()
        assert set(order) == {"X", "Y", "Z"}

    def test_subset_sort(self, dag: VCADDag) -> None:
        """Topological sort of a subset respects dependencies within subset."""
        dag.add_node(VCADNode(node_id="A", source_file="/a.cmp.oo"))
        dag.add_node(VCADNode(
            node_id="B", source_file="/b.cmp.oo",
            imports=[ImportRef(
                binding_name="a", selector="entity:1",
                extracts=["solid"], resolved_type="vcad", source_node_id="A",
            )],
        ))
        dag.add_node(VCADNode(node_id="C", source_file="/c.cmp.oo"))

        order = dag._topological_sort(["A", "B"])
        assert order == ["A", "B"]


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


class TestVCADDagCycleDetection:
    """Test cycle detection in DAG."""

    def test_no_cycle(self, dag: VCADDag) -> None:
        dag.add_node(VCADNode(node_id="A", source_file="/a.cmp.oo"))
        dag.add_node(VCADNode(
            node_id="B", source_file="/b.cmp.oo",
            imports=[ImportRef(
                binding_name="a", selector="entity:1",
                extracts=["solid"], resolved_type="vcad", source_node_id="A",
            )],
        ))

        assert dag.detect_cycle() is None

    def test_direct_cycle(self, dag: VCADDag) -> None:
        """A -> B -> A should be detected."""
        dag.add_node(VCADNode(
            node_id="A", source_file="/a.cmp.oo",
            imports=[ImportRef(
                binding_name="b", selector="entity:2",
                extracts=["solid"], resolved_type="vcad", source_node_id="B",
            )],
        ))
        dag.add_node(VCADNode(
            node_id="B", source_file="/b.cmp.oo",
            imports=[ImportRef(
                binding_name="a", selector="entity:1",
                extracts=["solid"], resolved_type="vcad", source_node_id="A",
            )],
        ))

        cycle = dag.detect_cycle()
        assert cycle is not None
        assert len(cycle) >= 2

    def test_empty_dag(self, dag: VCADDag) -> None:
        assert dag.detect_cycle() is None


# ---------------------------------------------------------------------------
# Revision tracking via DAG
# ---------------------------------------------------------------------------


class TestVCADDagRevisions:
    """Test revision tracking through the DAG interface."""

    def test_bump_revision(self, dag: VCADDag) -> None:
        dag.add_node(VCADNode(node_id="node-1", source_file="/a.cmp.oo"))

        rev1 = dag.bump_revision("node-1")
        assert rev1 == 1
        assert dag.current_revision("node-1") == 1

        rev2 = dag.bump_revision("node-1")
        assert rev2 == 2

    def test_should_apply(self, dag: VCADDag) -> None:
        dag.add_node(VCADNode(node_id="node-1", source_file="/a.cmp.oo"))

        rev = dag.bump_revision("node-1")
        assert dag.should_apply("node-1", rev) is True

    def test_stale_revision_dropped(self, dag: VCADDag) -> None:
        dag.add_node(VCADNode(node_id="node-1", source_file="/a.cmp.oo"))

        old_rev = dag.bump_revision("node-1")
        dag.bump_revision("node-1")  # bump again

        assert dag.should_apply("node-1", old_rev) is False

    def test_mark_applied(self, dag: VCADDag) -> None:
        dag.add_node(VCADNode(node_id="node-1", source_file="/a.cmp.oo"))

        rev = dag.bump_revision("node-1")
        dag.mark_applied("node-1", rev)

        node = dag.get_node("node-1")
        assert node.applied_revision == rev


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestVCADDagPersistence:
    """Test DAG persistence and loading."""

    def test_persist_and_load(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)

        dag.add_node(VCADNode(
            node_id="node-1",
            source_file="/test/a.cmp.oo",
            revision=3,
            applied_revision=3,
        ))
        dag.persist_state()

        # Load into fresh DAG
        state2 = VCADPersistentState(state_path=tmp_state_path)
        dag2 = VCADDag(state=state2)
        dag2.load_persisted_state()

        assert "node-1" in dag2.nodes
        assert dag2.nodes["node-1"].source_file == "/test/a.cmp.oo"
        assert dag2.nodes["node-1"].revision == 3
        assert dag2.current_revision("node-1") == 3

    def test_load_no_file(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)
        dag.load_persisted_state()  # Should not raise

        assert len(dag.nodes) == 0

    def test_persist_includes_status(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)

        dag.add_node(VCADNode(
            node_id="node-1",
            source_file="/missing.cmp.oo",
            status="degraded",
        ))
        dag.persist_state()

        # Verify persisted JSON
        with open(tmp_state_path) as f:
            data = json.load(f)
        assert data["nodes"]["node-1"]["status"] == "degraded"


# ---------------------------------------------------------------------------
# Reconciliation via DAG
# ---------------------------------------------------------------------------


class TestVCADDagReconciliation:
    """Test DAG reconciliation with SketchUp state."""

    def test_no_drift(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)

        dag.add_node(VCADNode(
            node_id="node-1",
            source_file=__file__,  # existing file
            revision=3,
            applied_revision=3,
        ))
        dag.persist_state()

        buckets = dag.reconcile_with_sketchup([{"node_id": "node-1"}])
        assert buckets["missing_node"] == []
        assert buckets["orphan_definition"] == []
        assert buckets["revision_gap"] == []
        assert buckets["source_missing"] == []

    def test_missing_node(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)

        dag.add_node(VCADNode(
            node_id="node-1",
            source_file=__file__,
            revision=1,
            applied_revision=1,
        ))
        dag.persist_state()

        # Reconcile with empty SketchUp state
        buckets = dag.reconcile_with_sketchup([])
        assert "node-1" in buckets["missing_node"]

    def test_orphan_definition(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)
        dag.persist_state()

        # SketchUp has a node we don't know about
        buckets = dag.reconcile_with_sketchup([{"node_id": "orphan-1"}])
        assert "orphan-1" in buckets["orphan_definition"]
        # Orphan should be added to DAG as orphan status
        assert "orphan-1" in dag.nodes
        assert dag.nodes["orphan-1"].status == "orphan"

    def test_source_missing_marks_degraded(self, tmp_state_path: str) -> None:
        # Create a temp file then delete it
        with tempfile.NamedTemporaryFile(suffix=".cmp.oo", delete=False) as f:
            missing_path = f.name
        os.unlink(missing_path)

        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)

        dag.add_node(VCADNode(
            node_id="node-1",
            source_file=missing_path,
            revision=2,
            applied_revision=2,
            status="active",
        ))
        dag.persist_state()

        buckets = dag.reconcile_with_sketchup([{"node_id": "node-1"}])
        assert "node-1" in buckets["source_missing"]
        assert dag.nodes["node-1"].status == "degraded"

    def test_revision_gap(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)

        dag.add_node(VCADNode(
            node_id="node-1",
            source_file=__file__,
            revision=5,
            applied_revision=3,
        ))
        dag.persist_state()

        buckets = dag.reconcile_with_sketchup([{"node_id": "node-1"}])
        assert "node-1" in buckets["revision_gap"]

    def test_full_reconciliation_scenario(self, tmp_state_path: str) -> None:
        """Seed persisted state, reconcile with SketchUp snapshot, verify all drift buckets."""
        # Create a temp file then delete it for source_missing
        with tempfile.NamedTemporaryFile(suffix=".cmp.oo", delete=False) as f:
            missing_path = f.name
        os.unlink(missing_path)

        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)

        # node-1: exists in both, source exists, no gap -> ok
        dag.add_node(VCADNode(
            node_id="node-1",
            source_file=__file__,
            revision=5,
            applied_revision=5,
        ))
        # node-2: exists in persisted but source is missing -> source_missing
        dag.add_node(VCADNode(
            node_id="node-2",
            source_file=missing_path,
            revision=3,
            applied_revision=3,
        ))
        # node-3: exists in persisted but not in SketchUp -> missing_node
        dag.add_node(VCADNode(
            node_id="node-3",
            source_file=__file__,
            revision=2,
            applied_revision=2,
        ))
        # node-4: has revision gap
        dag.add_node(VCADNode(
            node_id="node-4",
            source_file=__file__,
            revision=7,
            applied_revision=4,
        ))
        dag.persist_state()

        # SketchUp has: node-1, node-2, node-4, node-5 (orphan)
        su_nodes = [
            {"node_id": "node-1"},
            {"node_id": "node-2"},
            {"node_id": "node-4"},
            {"node_id": "node-5"},
        ]

        buckets = dag.reconcile_with_sketchup(su_nodes)

        assert "node-3" in buckets["missing_node"]
        assert "node-5" in buckets["orphan_definition"]
        assert "node-2" in buckets["source_missing"]
        assert "node-4" in buckets["revision_gap"]

        # node-2 should be degraded
        assert dag.nodes["node-2"].status == "degraded"
        # node-5 should be orphan
        assert dag.nodes["node-5"].status == "orphan"

    def test_source_missing_deterministic(self, tmp_state_path: str) -> None:
        """Verify source_missing nodes return SOURCE_FILE_MISSING deterministically."""
        with tempfile.NamedTemporaryFile(suffix=".cmp.oo", delete=False) as f:
            missing_path = f.name
        os.unlink(missing_path)

        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)

        dag.add_node(VCADNode(
            node_id="node-1",
            source_file=missing_path,
            revision=1,
            applied_revision=1,
            status="active",
        ))
        dag.persist_state()

        su_nodes = [{"node_id": "node-1"}]

        # Run reconciliation multiple times
        for _ in range(3):
            buckets = dag.reconcile_with_sketchup(su_nodes)
            assert "node-1" in buckets["source_missing"]
            assert dag.nodes["node-1"].status == "degraded"

    def test_persisted_state_survives_reconciliation(self, tmp_state_path: str) -> None:
        """After reconciliation, state is persisted and loadable."""
        with tempfile.NamedTemporaryFile(suffix=".cmp.oo", delete=False) as f:
            missing_path = f.name
        os.unlink(missing_path)

        state = VCADPersistentState(state_path=tmp_state_path)
        dag = VCADDag(state=state)

        dag.add_node(VCADNode(
            node_id="node-1",
            source_file=missing_path,
            revision=2,
            applied_revision=2,
        ))
        dag.persist_state()

        dag.reconcile_with_sketchup([{"node_id": "node-1"}])

        # Load fresh
        state2 = VCADPersistentState(state_path=tmp_state_path)
        dag2 = VCADDag(state=state2)
        dag2.load_persisted_state()

        assert dag2.nodes["node-1"].status == "degraded"
        assert dag2.current_revision("node-1") == 2


# ---------------------------------------------------------------------------
# Import ref handling
# ---------------------------------------------------------------------------


class TestImportRef:
    """Test ImportRef dataclass."""

    def test_basic_import_ref(self) -> None:
        ref = ImportRef(
            binding_name="plate_dims",
            selector="entity:12345",
            extracts=["dims"],
            resolved_type="native",
        )
        assert ref.binding_name == "plate_dims"
        assert ref.selector == "entity:12345"
        assert ref.extracts == ["dims"]
        assert ref.resolved_type == "native"
        assert ref.source_node_id is None

    def test_vcad_import_ref(self) -> None:
        ref = ImportRef(
            binding_name="base_solid",
            selector="entity:67890",
            extracts=["solid"],
            resolved_type="vcad",
            source_node_id="base-plate",
        )
        assert ref.resolved_type == "vcad"
        assert ref.source_node_id == "base-plate"


# ---------------------------------------------------------------------------
# Mixed native + vcad imports
# ---------------------------------------------------------------------------


class TestVCADDagMixedImports:
    """Test DAG with both native and vcad imports."""

    def test_only_vcad_imports_create_edges(self, dag: VCADDag) -> None:
        """Native imports don't create DAG edges for downstream."""
        dag.add_node(VCADNode(node_id="A", source_file="/a.cmp.oo"))
        dag.add_node(VCADNode(
            node_id="B",
            source_file="/b.cmp.oo",
            imports=[
                ImportRef(
                    binding_name="native_data",
                    selector="entity:100",
                    extracts=["dims"],
                    resolved_type="native",
                ),
                ImportRef(
                    binding_name="vcad_solid",
                    selector="entity:200",
                    extracts=["solid"],
                    resolved_type="vcad",
                    source_node_id="A",
                ),
            ],
        ))

        downstream = dag.get_downstream("A")
        assert downstream == ["B"]

        # Entity 100 dependents should include B (native import)
        entity_deps = dag.get_dependents_of_entity("100")
        assert "B" in entity_deps

    def test_entity_dependents_includes_vcad_backed(self, dag: VCADDag) -> None:
        """get_dependents_of_entity works for vcad-backed entities too."""
        dag.add_node(VCADNode(node_id="A", source_file="/a.cmp.oo"))
        dag.add_node(VCADNode(
            node_id="B",
            source_file="/b.cmp.oo",
            imports=[ImportRef(
                binding_name="a_solid",
                selector="entity:200",
                extracts=["solid"],
                resolved_type="vcad",
                source_node_id="A",
            )],
        ))

        deps = dag.get_dependents_of_entity("200")
        assert "B" in deps
