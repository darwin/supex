"""E2E integration tests for vcad pipeline using mock sidecar + su-mock.

Tests are named with 'vcad_e2e_mock' to match the verification filter:
    uv run pytest tests/ -v -k vcad_e2e_mock

Coverage:
    - Sidecar eval_repl_with_imports / eval_file via MockVCADSidecar
    - Full pipeline: eval -> OBJ -> SketchUp import via su-mock
    - Security: auth token, path traversal
    - State reconciliation and recovery
    - Error propagation with standardized error_code values
"""

import os

import pytest

from supex_driver.connection.vcad_connection import VCADConnection
from supex_driver.connection.vcad_exceptions import (
    VCADProtocolError,
    VCADRemoteError,
)
from supex_driver.connection.vcad_state import (
    EvalJob,
    EvalQueue,
    NodeState,
    RevisionTracker,
    VCADPersistentState,
    VCADReconciler,
)
from tests.helpers.mock_vcad_sidecar import MockVCADSidecar

# ---------------------------------------------------------------------------
# Minimal OBJ content for mock import
# ---------------------------------------------------------------------------

CUBE_OBJ = """\
# unit cube
v 0.0 0.0 0.0
v 10.0 0.0 0.0
v 10.0 10.0 0.0
v 0.0 10.0 0.0
v 0.0 0.0 10.0
v 10.0 0.0 10.0
v 10.0 10.0 10.0
v 0.0 10.0 10.0
f 1 2 3 4
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
"""


def write_obj(directory, name="mesh.obj"):
    """Write a minimal OBJ file and return its path."""
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        f.write(CUBE_OBJ)
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sidecar():
    """Start a MockVCADSidecar on a random port."""
    server = MockVCADSidecar()
    server.start()
    yield server
    server.stop()


@pytest.fixture
def vcad_conn(mock_sidecar):
    """VCADConnection wired to the mock sidecar."""
    conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e-test")
    yield conn
    conn.disconnect()


@pytest.fixture
def obj_dir(tmp_path):
    """Temp directory with a pre-written OBJ file."""
    write_obj(str(tmp_path))
    return str(tmp_path)


@pytest.fixture
def tmp_state_path(tmp_path):
    """Temporary path for persistent state file."""
    return str(tmp_path / "vcad-state.json")


# ---------------------------------------------------------------------------
# Sidecar eval_repl_with_imports / eval_file (via mock sidecar TCP)
# ---------------------------------------------------------------------------


class TestVCADE2EMockSidecarEval:
    """Test sidecar evaluation via MockVCADSidecar over real TCP."""

    def test_vcad_e2e_mock_eval_repl(self, mock_sidecar):
        """eval_repl_with_imports returns display string."""
        mock_sidecar.set_response(
            "tools/call",
            result={"display": "Cube(10.0, 10.0, 10.0)"},
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        result = conn.eval_repl_with_imports(
            transformed_source="[cube 10.0 10.0 10.0]",
            imports={},
        )

        assert "display" in result
        conn.disconnect()

    def test_vcad_e2e_mock_eval_file(self, mock_sidecar, tmp_path):
        """eval_file with a .skp.oo file returns eval result."""
        loon_file = tmp_path / "test.skp.oo"
        loon_file.write_text("[pipe [cube 50.0 10.0 30.0] [fillet 2.0]]")
        obj_path = write_obj(str(tmp_path))

        mock_sidecar.set_response(
            "tools/call",
            result={
                "obj_path": obj_path,
                "volume": 14800.0,
                "surface_area": 5200.0,
                "is_empty": False,
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        result = conn.eval_file(str(loon_file))

        assert result["volume"] > 0
        assert os.path.exists(result["obj_path"])
        conn.disconnect()

    def test_vcad_e2e_mock_eval_repl_error(self, mock_sidecar):
        """eval_repl_with_imports with parse error returns standardized error_code."""
        mock_sidecar.set_response(
            "tools/call",
            error={
                "code": -32000,
                "message": "Loon parse error: unexpected ]",
                "data": {"error_code": "PARSE_ERROR"},
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        with pytest.raises(VCADRemoteError) as exc_info:
            conn.eval_repl_with_imports(
                transformed_source="[invalid ]",
                imports={},
            )

        assert exc_info.value.code == -32000
        assert "parse error" in exc_info.value.message.lower()
        conn.disconnect()


# ---------------------------------------------------------------------------
# Security checks
# ---------------------------------------------------------------------------


class TestVCADE2EMockSecurity:
    """Security validation: auth tokens, path traversal, error_code values."""

    def test_vcad_e2e_mock_auth_invalid_token(self):
        """Token mismatch on hello returns AUTH_INVALID."""
        server = MockVCADSidecar()
        # Simulate auth-required sidecar: respond with error on wrong token
        server.responses["hello"] = {
            "result": None,
            "error": {
                "code": -32000,
                "message": "Invalid authentication token",
                "data": {"error_code": "AUTH_INVALID"},
            },
        }
        server.start()
        try:
            conn = VCADConnection(
                host="127.0.0.1",
                port=server.port,
                agent="e2e",
                token="wrong-token",
            )
            result = conn.connect()
            assert result is False
        finally:
            server.stop()

    def test_vcad_e2e_mock_path_traversal_rejected(self, mock_sidecar):
        """Path traversal attempts return PATH_NOT_ALLOWED error_code."""
        mock_sidecar.set_response(
            "tools/call",
            error={
                "code": -32000,
                "message": "Path traversal not allowed",
                "data": {"error_code": "PATH_NOT_ALLOWED"},
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        with pytest.raises(VCADRemoteError) as exc_info:
            conn.eval_file("../outside/test.skp.oo")

        assert exc_info.value.code == -32000
        assert exc_info.value.data.get("error_code") == "PATH_NOT_ALLOWED"
        conn.disconnect()

    def test_vcad_e2e_mock_standardized_error_codes(self, mock_sidecar):
        """Verify standardized error_code values in responses."""
        error_scenarios = [
            {
                "code": -32000,
                "message": "No geometry produced",
                "data": {"error_code": "NO_GEOMETRY"},
            },
            {
                "code": -32000,
                "message": "Multiple parts unsupported",
                "data": {"error_code": "MULTI_PART_UNSUPPORTED"},
            },
            {
                "code": -32000,
                "message": "Queue full",
                "data": {"error_code": "VCAD_QUEUE_FULL"},
            },
        ]

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")

        for scenario in error_scenarios:
            mock_sidecar.set_response("tools/call", error=scenario)

            with pytest.raises(VCADRemoteError) as exc_info:
                conn.eval_repl_with_imports(
                    transformed_source="[cube 1.0 1.0 1.0]",
                    imports={},
                )

            assert exc_info.value.code == scenario["code"]
            assert (
                exc_info.value.data.get("error_code") == scenario["data"]["error_code"]
            )

            # Force reconnect for next iteration
            conn.disconnect()
            conn.sock = None
            conn._identified = False


# ---------------------------------------------------------------------------
# Full pipeline: eval -> OBJ -> SketchUp import (su-mock)
# ---------------------------------------------------------------------------


@pytest.mark.su_mock
class TestVCADE2EMockFullPipeline:
    """Full E2E pipeline tests via su-mock + mock sidecar.

    These tests exercise the real Ruby bridge server running against
    mock SketchUp API, combined with MockVCADSidecar for the sidecar side.
    """

    def test_vcad_e2e_mock_place_and_list(self, su_mock, mock_sidecar, tmp_path):
        """Place a vcad node via su-mock and verify it appears in list."""
        # Write OBJ file that su-mock can import
        obj_path = write_obj(str(tmp_path), "bracket.obj")

        # Configure mock sidecar to return the OBJ
        mock_sidecar.set_response(
            "tools/call",
            result={
                "obj_path": obj_path,
                "volume": 1500.0,
                "surface_area": 900.0,
                "is_empty": False,
            },
        )

        # Eval via mock sidecar
        vcad_conn = VCADConnection(
            host="127.0.0.1", port=mock_sidecar.port, agent="e2e"
        )
        eval_result = vcad_conn.eval_file(str(tmp_path / "bracket.skp.oo"))
        assert eval_result["obj_path"] == obj_path

        # Place in SketchUp via su-mock (real Ruby bridge)
        place_result = su_mock.send_command(
            method="place_vcad_node",
            params={
                "obj_path": obj_path,
                "node_id": "e2e-bracket",
                "source_file": str(tmp_path / "bracket.skp.oo"),
                "position": [0, 0, 0],
            },
        )
        assert place_result["success"] is True
        assert place_result["node_id"] == "e2e-bracket"

        # Verify node appears in list
        nodes = su_mock.send_command(method="list_vcad_nodes", params={})
        assert isinstance(nodes, list)
        assert any(n["node_id"] == "e2e-bracket" for n in nodes)

        vcad_conn.disconnect()

    def test_vcad_e2e_mock_update_node(self, su_mock, mock_sidecar, tmp_path):
        """Place a node, then update it with new geometry."""
        obj_path_v1 = write_obj(str(tmp_path), "v1.obj")
        obj_path_v2 = write_obj(str(tmp_path), "v2.obj")
        source_file = str(tmp_path / "part.skp.oo")

        mock_sidecar.set_response(
            "tools/call",
            result={"obj_path": obj_path_v1, "volume": 1000.0, "is_empty": False},
        )

        # Place initial version
        vcad_conn = VCADConnection(
            host="127.0.0.1", port=mock_sidecar.port, agent="e2e"
        )
        vcad_conn.eval_file(source_file)

        place_result = su_mock.send_command(
            method="place_vcad_node",
            params={
                "obj_path": obj_path_v1,
                "node_id": "e2e-part",
                "source_file": source_file,
            },
        )
        assert place_result["success"] is True

        # Verify version 1
        node = su_mock.send_command(
            method="get_vcad_node", params={"node_id": "e2e-part"}
        )
        assert node["version"] == 1

        # Update with new OBJ
        update_result = su_mock.send_command(
            method="update_vcad_node",
            params={
                "obj_path": obj_path_v2,
                "node_id": "e2e-part",
                "source_file": source_file,
            },
        )
        assert update_result["success"] is True
        assert update_result["version"] == 2

        vcad_conn.disconnect()

    def test_vcad_e2e_mock_list_empty_model(self, su_mock):
        """Empty model returns empty vcad node list."""
        nodes = su_mock.send_command(method="list_vcad_nodes", params={})
        assert nodes == []


# ---------------------------------------------------------------------------
# Restart/recovery: driver state reconciliation
# ---------------------------------------------------------------------------


class TestVCADE2EMockRecovery:
    """Restart and recovery scenarios with state reconciliation."""

    def test_vcad_e2e_mock_driver_restart_reconcile(self, tmp_state_path):
        """Restart driver: persisted state reconciles with runtime.

        Simulates: driver crashes, restarts, loads persisted state,
        queries SketchUp for current nodes, classifies drift, and reconciles.
        """
        # Pre-crash state: two active nodes
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(
            NodeState(
                node_id="node-a",
                source_file=__file__,  # existing file
                revision=5,
                applied_revision=5,
                status="active",
            )
        )
        state.set_node(
            NodeState(
                node_id="node-b",
                source_file=__file__,
                revision=3,
                applied_revision=3,
                status="active",
            )
        )
        state.save()

        # Simulate restart: load persisted state
        loaded = VCADPersistentState(state_path=tmp_state_path)
        assert loaded.load() is True

        # SketchUp reports both nodes still present
        runtime_nodes = [{"node_id": "node-a"}, {"node_id": "node-b"}]

        drift = VCADReconciler.classify_drift(loaded.all_nodes(), runtime_nodes)
        assert len(drift) == 0

        result = VCADReconciler.reconcile(loaded, drift)
        assert result["status"] == "ok"

        # Rebuild revision tracker
        tracker = RevisionTracker()
        VCADReconciler.rebuild_revisions(loaded, tracker)
        assert tracker.current_revision("node-a") == 5
        assert tracker.current_revision("node-b") == 3

    def test_vcad_e2e_mock_sidecar_restart_no_duplicates(self, tmp_state_path):
        """Restart sidecar during active queue: no duplicate imports.

        Verifies that supersede-aware queue pruning prevents stale results
        from being applied after sidecar restart.
        """
        tracker = RevisionTracker()
        queue = EvalQueue(max_size=10)

        # Pre-restart state
        tracker.set_revision("node-1", 3)
        tracker.set_revision("node-2", 2)

        # Queue pending evals (pre-restart work)
        queue.enqueue(EvalJob(node_id="node-1", revision=3, source="pre-restart"))
        queue.enqueue(EvalJob(node_id="node-2", revision=2, source="pre-restart"))

        # Sidecar restarts -> bump all revisions for cache rebuild
        new_rev_1 = tracker.next_revision("node-1")  # 4
        new_rev_2 = tracker.next_revision("node-2")  # 3
        queue.enqueue(EvalJob(node_id="node-1", revision=new_rev_1, source="rebuilt"))
        queue.enqueue(EvalJob(node_id="node-2", revision=new_rev_2, source="rebuilt"))

        # Process queue: only rebuilt jobs should execute
        executed = []
        while True:
            job = queue.get_next()
            if job is None:
                break
            executed.append(job)

        assert len(executed) == 2
        executed_ids = {(j.node_id, j.revision) for j in executed}
        assert ("node-1", new_rev_1) in executed_ids
        assert ("node-2", new_rev_2) in executed_ids

        # Old revisions must not apply
        assert tracker.should_apply("node-1", 3) is False
        assert tracker.should_apply("node-2", 2) is False
        # New revisions apply
        assert tracker.should_apply("node-1", new_rev_1) is True
        assert tracker.should_apply("node-2", new_rev_2) is True

    def test_vcad_e2e_mock_reconcile_with_orphan_and_missing(self, tmp_state_path):
        """Reconciliation handles orphan definitions and missing sources."""
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(
            NodeState(
                node_id="node-a",
                source_file=__file__,
                revision=5,
                applied_revision=5,
            )
        )
        state.set_node(
            NodeState(
                node_id="node-gone",
                source_file="/nonexistent/gone.skp.oo",
                revision=2,
                applied_revision=2,
                status="active",
            )
        )
        state.save()

        loaded = VCADPersistentState(state_path=tmp_state_path)
        loaded.load()

        # SketchUp has node-a, node-gone, plus an orphan
        runtime_nodes = [
            {"node_id": "node-a"},
            {"node_id": "node-gone"},
            {"node_id": "node-orphan"},
        ]

        drift = VCADReconciler.classify_drift(loaded.all_nodes(), runtime_nodes)
        drift_types = {d.drift_type for d in drift}

        assert "source_missing" in drift_types
        assert "orphan_definition" in drift_types

        result = VCADReconciler.reconcile(loaded, drift)
        assert result["status"] == "degraded"

        # Verify error_code in actions
        actions = result.get("actions", [])
        degraded_actions = [a for a in actions if a["action"] == "mark_degraded"]
        assert len(degraded_actions) >= 1
        assert any(a["error_code"] == "SOURCE_FILE_MISSING" for a in degraded_actions)

    def test_vcad_e2e_mock_revision_gap_triggers_cascade(self, tmp_state_path):
        """Revision gap (applied < current) triggers cascade update."""
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(
            NodeState(
                node_id="stale-node",
                source_file=__file__,
                revision=5,
                applied_revision=2,  # gap!
            )
        )
        state.save()

        loaded = VCADPersistentState(state_path=tmp_state_path)
        loaded.load()

        runtime_nodes = [{"node_id": "stale-node"}]
        drift = VCADReconciler.classify_drift(loaded.all_nodes(), runtime_nodes)

        assert len(drift) == 1
        assert drift[0].drift_type == "revision_gap"
        assert drift[0].node_id == "stale-node"


# ---------------------------------------------------------------------------
# Viewer reconnect
# ---------------------------------------------------------------------------


class TestVCADE2EMockViewerReconnect:
    """Viewer reconnect after burst of updates."""

    def test_vcad_e2e_mock_revision_matches_after_burst(self, tmp_state_path):
        """After burst of updates, latest revision is consistent.

        Simulates rapid eval bursts and verifies that the final state
        reflects only the latest revision for each node.
        """
        tracker = RevisionTracker()
        queue = EvalQueue(max_size=100)

        # Simulate burst: 10 rapid updates for 3 nodes
        for node_idx in range(3):
            node_id = f"burst-node-{node_idx}"
            for rev in range(1, 11):
                tracker.next_revision(node_id)
                queue.enqueue(EvalJob(node_id=node_id, revision=rev, source=f"v{rev}"))

        # Process queue: only latest revision per node should execute
        executed = {}
        while True:
            job = queue.get_next()
            if job is None:
                break
            executed[job.node_id] = job.revision

        # Each node should only have its latest revision executed
        for node_idx in range(3):
            node_id = f"burst-node-{node_idx}"
            assert executed[node_id] == 10
            assert tracker.current_revision(node_id) == 10

            # Only latest applies, all older are stale
            assert tracker.should_apply(node_id, 10) is True
            for old_rev in range(1, 10):
                assert tracker.should_apply(node_id, old_rev) is False


# ---------------------------------------------------------------------------
# Protocol negotiation E2E
# ---------------------------------------------------------------------------


class TestVCADE2EMockProtocol:
    """Protocol negotiation and version checks over real TCP."""

    def test_vcad_e2e_mock_protocol_version_negotiated(self, mock_sidecar):
        """Successful hello negotiates protocol version and capabilities."""
        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        result = conn.connect()

        assert result is True
        assert conn._protocol_version == "1.0"
        assert "eval" in conn._capabilities
        assert "inspect" in conn._capabilities
        conn.disconnect()

    def test_vcad_e2e_mock_protocol_mismatch(self):
        """Major version mismatch triggers PROTOCOL_MISMATCH error."""
        server = MockVCADSidecar()
        server.protocol_version = "2.0"
        server.start()

        try:
            conn = VCADConnection(host="127.0.0.1", port=server.port, agent="e2e")
            with pytest.raises(VCADProtocolError) as exc_info:
                conn.connect()

            assert exc_info.value.error_code == "PROTOCOL_MISMATCH"
            assert "driver=" in str(exc_info.value)
            assert "sidecar=2.0" in str(exc_info.value)
        finally:
            server.stop()

    def test_vcad_e2e_mock_connection_reuse(self, mock_sidecar):
        """Multiple commands reuse single connection (one hello)."""
        mock_sidecar.set_response("tools/call", result={"ok": True})

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")

        for _ in range(5):
            conn.send_command("vcad.eval_repl_with_imports", {"transformed_source": "[cube 1.0 1.0 1.0]"})

        hello_count = sum(
            1 for r in mock_sidecar.requests if r.get("method") == "hello"
        )
        assert hello_count == 1
        conn.disconnect()
