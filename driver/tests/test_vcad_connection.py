"""Tests for vcad connection, sidecar lifecycle, and state management."""

import json
import os
import tempfile
import threading
import time
from unittest.mock import Mock, patch

import pytest

from supex_driver.connection.vcad_connection import (
    PROTOCOL_VERSION,
    VCADConnection,
    _parse_major_version,
)
from supex_driver.connection.vcad_dag import VCADDag
from supex_driver.connection.vcad_exceptions import (
    CAPABILITY_UNAVAILABLE,
    PROTOCOL_MISMATCH,
    VCADCapabilityError,
    VCADConnectionError,
    VCADProtocolError,
    VCADRemoteError,
)
from supex_driver.connection.vcad_sidecar import VCADSidecar
from supex_driver.connection.vcad_state import (
    EvalJob,
    EvalQueue,
    NodeState,
    RevisionTracker,
    TriggerCoalescer,
    VCADPersistentState,
    VCADReconciler,
)
from tests.helpers.mock_vcad_sidecar import MockVCADSidecar

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sidecar():
    """Create and start a mock vcad sidecar server."""
    server = MockVCADSidecar()
    server.start()
    yield server
    server.stop()


@pytest.fixture
def tmp_state_path(tmp_path):
    """Temporary path for persistent state file."""
    return str(tmp_path / "vcad-state.json")


# ---------------------------------------------------------------------------
# VCADConnection — basic
# ---------------------------------------------------------------------------


class TestVCADConnectionBasic:
    """Test VCADConnection initialization and basic behavior."""

    def test_initialization(self) -> None:
        conn = VCADConnection(host="localhost", port=9877)
        assert conn.host == "localhost"
        assert conn.port == 9877
        assert conn.timeout == 30.0
        assert conn.sock is None

    @patch("socket.socket")
    def test_connect_success(self, mock_socket: Mock) -> None:
        mock_sock = Mock()
        mock_socket.return_value = mock_sock

        hello_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "success": True,
                "protocol_version": "1.0",
                "capabilities": ["eval", "inspect"],
                "limits": {"max_source_bytes": 1048576},
            },
            "id": "hello",
        }).encode("utf-8") + b"\n"
        mock_sock.recv.return_value = hello_response

        conn = VCADConnection(host="localhost", port=9877, agent="test")
        result = conn.connect()

        assert result is True
        assert conn._identified is True
        assert conn._protocol_version == "1.0"
        assert conn._capabilities == ["eval", "inspect"]
        assert conn._limits == {"max_source_bytes": 1048576}

    @patch("socket.socket")
    def test_connect_failure(self, mock_socket: Mock) -> None:
        mock_socket.side_effect = ConnectionRefusedError("Connection refused")

        conn = VCADConnection(host="localhost", port=9877)
        result = conn.connect()

        assert result is False
        assert conn.sock is None

    def test_disconnect(self) -> None:
        mock_sock = Mock()
        conn = VCADConnection(host="localhost", port=9877)
        conn.sock = mock_sock

        conn.disconnect()

        mock_sock.close.assert_called_once()
        assert conn.sock is None

    def test_disconnect_with_error(self) -> None:
        mock_sock = Mock()
        mock_sock.close.side_effect = OSError("Socket error")

        conn = VCADConnection(host="localhost", port=9877)
        conn.sock = mock_sock

        conn.disconnect()
        assert conn.sock is None


# ---------------------------------------------------------------------------
# VCADConnection — protocol negotiation
# ---------------------------------------------------------------------------


class TestVCADConnectionProtocol:
    """Test protocol version negotiation and capability checking."""

    def test_parse_major_version(self) -> None:
        assert _parse_major_version("1.0") == 1
        assert _parse_major_version("2.3") == 2
        assert _parse_major_version("0.1") == 0
        assert _parse_major_version("invalid") == -1

    @patch("socket.socket")
    def test_protocol_mismatch_fails_fast(self, mock_socket: Mock) -> None:
        """Major version mismatch must fail with PROTOCOL_MISMATCH."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock

        hello_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "success": True,
                "protocol_version": "2.0",
                "capabilities": ["eval"],
                "limits": {},
            },
            "id": "hello",
        }).encode("utf-8") + b"\n"
        mock_sock.recv.return_value = hello_response

        conn = VCADConnection(host="localhost", port=9877)

        with pytest.raises(VCADProtocolError) as exc_info:
            conn.connect()

        assert exc_info.value.error_code == PROTOCOL_MISMATCH
        assert "driver=" in str(exc_info.value)
        assert "sidecar=2.0" in str(exc_info.value)
        assert exc_info.value.details["expected_protocol"] == PROTOCOL_VERSION
        assert exc_info.value.details["actual_protocol"] == "2.0"

    @patch("socket.socket")
    def test_protocol_mismatch_no_fallback(self, mock_socket: Mock) -> None:
        """No downgrade/fallback attempt on mismatch."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock

        hello_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "success": True,
                "protocol_version": "99.0",
                "capabilities": [],
                "limits": {},
            },
            "id": "hello",
        }).encode("utf-8") + b"\n"
        mock_sock.recv.return_value = hello_response

        conn = VCADConnection(host="localhost", port=9877)

        with pytest.raises(VCADProtocolError) as exc_info:
            conn.connect()

        assert exc_info.value.error_code == PROTOCOL_MISMATCH
        # Verify no second hello was sent (no downgrade attempt)
        assert mock_sock.sendall.call_count == 1

    @patch("socket.socket")
    def test_capability_unavailable(self, mock_socket: Mock) -> None:
        """Missing capability must raise CAPABILITY_UNAVAILABLE with details."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock

        hello_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "success": True,
                "protocol_version": "1.0",
                "capabilities": ["eval"],
                "limits": {},
            },
            "id": "hello",
        }).encode("utf-8") + b"\n"
        mock_sock.recv.return_value = hello_response

        conn = VCADConnection(host="localhost", port=9877)
        conn.connect()

        with pytest.raises(VCADCapabilityError) as exc_info:
            conn.require_capability("adt_cache", "cross_node_import")

        assert exc_info.value.error_code == CAPABILITY_UNAVAILABLE
        assert exc_info.value.required_capability == "adt_cache"
        assert exc_info.value.negotiated_capabilities == ["eval"]
        assert exc_info.value.operation == "cross_node_import"
        assert exc_info.value.details["required_capability"] == "adt_cache"
        assert exc_info.value.details["negotiated_capabilities"] == ["eval"]
        assert exc_info.value.details["operation"] == "cross_node_import"

    @patch("socket.socket")
    def test_capabilities_populated_on_success(self, mock_socket: Mock) -> None:
        """Successful negotiation populates capabilities and limits."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock

        capabilities = ["eval", "inspect", "adt_cache"]
        limits = {"max_source_bytes": 2097152, "max_eval_time_ms": 60000}

        hello_response = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "success": True,
                "protocol_version": "1.0",
                "capabilities": capabilities,
                "limits": limits,
            },
            "id": "hello",
        }).encode("utf-8") + b"\n"
        mock_sock.recv.return_value = hello_response

        conn = VCADConnection(host="localhost", port=9877)
        conn.connect()

        assert conn._capabilities == capabilities
        assert conn._limits == limits
        # Should not raise for available capability
        conn.require_capability("eval", "eval_with_imports")

    def test_hello_includes_protocol_version(self, mock_sidecar: MockVCADSidecar) -> None:
        """Hello handshake includes protocol_version."""
        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port)
        conn.connect()
        conn.disconnect()

        assert len(mock_sidecar.requests) == 1
        hello_req = mock_sidecar.requests[0]
        assert hello_req["method"] == "hello"
        assert hello_req["params"]["protocol_version"] == PROTOCOL_VERSION

    def test_hello_includes_workspace_and_token(self, mock_sidecar: MockVCADSidecar) -> None:
        """Hello handshake includes workspace and token when configured."""
        conn = VCADConnection(
            host="127.0.0.1",
            port=mock_sidecar.port,
            workspace="/test/workspace",
            token="secret-token",
        )
        conn.connect()
        conn.disconnect()

        hello_req = mock_sidecar.requests[0]
        assert hello_req["params"]["workspace"] == "/test/workspace"
        assert hello_req["params"]["token"] == "secret-token"


# ---------------------------------------------------------------------------
# VCADConnection — integration with mock sidecar
# ---------------------------------------------------------------------------


class TestVCADConnectionIntegration:
    """Integration tests with mock vcad sidecar."""

    def test_eval_with_imports_display(self, mock_sidecar: MockVCADSidecar) -> None:
        mock_sidecar.set_response(
            "tools/call",
            result={"display": "Cube(10.0, 10.0, 10.0)"},
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port)
        result = conn.eval_with_imports(
            transformed_source="[cube 10.0 10.0 10.0]",
            imports={},
            display=True,
            export_mesh=False,
        )

        assert "display" in result
        # Verify the request was wrapped as tools/call
        tool_call = mock_sidecar.requests[-1]
        assert tool_call["method"] == "tools/call"
        assert tool_call["params"]["name"] == "vcad.eval_with_imports"
        assert tool_call["params"]["arguments"]["transformed_source"] == "[cube 10.0 10.0 10.0]"
        assert tool_call["params"]["arguments"]["display"] is True
        assert tool_call["params"]["arguments"]["export_mesh"] is False
        conn.disconnect()

    def test_eval_with_imports_mesh(self, mock_sidecar: MockVCADSidecar) -> None:
        mock_sidecar.set_response(
            "tools/call",
            result={"mesh": {"vertices": [0.0], "indices": [0]}},
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port)
        result = conn.eval_with_imports(
            transformed_source="[cube 10.0 10.0 10.0]",
            export_mesh=True,
        )

        assert "mesh" in result
        tool_call = mock_sidecar.requests[-1]
        assert tool_call["params"]["name"] == "vcad.eval_with_imports"
        assert tool_call["params"]["arguments"]["transformed_source"] == "[cube 10.0 10.0 10.0]"
        conn.disconnect()

    def test_remote_error(self, mock_sidecar: MockVCADSidecar) -> None:
        mock_sidecar.set_response(
            "tools/call",
            error={"code": -32000, "message": "Loon parse error"},
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port)

        with pytest.raises(VCADRemoteError) as exc_info:
            conn.eval_with_imports(
                transformed_source="invalid code",
                imports={},
                display=True,
                export_mesh=False,
            )

        assert exc_info.value.code == -32000
        assert "parse error" in exc_info.value.message
        conn.disconnect()

    def test_connection_reuse(self, mock_sidecar: MockVCADSidecar) -> None:
        mock_sidecar.set_response("tools/call", result={"ok": True})

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port)

        for _ in range(5):
            conn.send_command("vcad.eval_with_imports", {"transformed_source": "test"})

        hello_count = sum(
            1 for r in mock_sidecar.requests if r.get("method") == "hello"
        )
        assert hello_count == 1
        conn.disconnect()

    def test_send_command_raises_when_not_connected(self) -> None:
        conn = VCADConnection(host="localhost", port=1)

        with (
            patch.object(conn, "connect", return_value=True),
            patch.object(conn, "_is_connection_healthy", return_value=False),
        ):
            conn.sock = None

            with pytest.raises(VCADConnectionError) as exc_info:
                conn.send_command("ping")

            assert "Socket not initialized" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Stale-result guard
# ---------------------------------------------------------------------------


class TestVCADConnectionStaleGuard:
    """Test revision tracking and stale-result protection."""

    def test_basic_revision_tracking(self) -> None:
        tracker = RevisionTracker()

        assert tracker.current_revision("node-1") == 0
        rev1 = tracker.next_revision("node-1")
        assert rev1 == 1
        assert tracker.current_revision("node-1") == 1

        rev2 = tracker.next_revision("node-1")
        assert rev2 == 2
        assert tracker.current_revision("node-1") == 2

    def test_should_apply_current_revision(self) -> None:
        tracker = RevisionTracker()
        rev = tracker.next_revision("node-1")

        assert tracker.should_apply("node-1", rev) is True
        assert tracker.stale_dropped == 0

    def test_stale_result_dropped(self) -> None:
        """Enqueue two eval requests for same node (slow old + fast new).
        Verify only new revision is applied; old result is dropped.
        """
        tracker = RevisionTracker()

        # Simulate: two evals enqueued, old one (rev 1) and new one (rev 2)
        old_rev = tracker.next_revision("node-1")  # rev 1
        new_rev = tracker.next_revision("node-1")  # rev 2

        # New result arrives first — should apply (matches current)
        assert tracker.should_apply("node-1", new_rev) is True
        assert tracker.stale_dropped == 0

        # Old result arrives late — should be dropped
        assert tracker.should_apply("node-1", old_rev) is False
        assert tracker.stale_dropped == 1

    def test_multiple_stale_drops(self) -> None:
        tracker = RevisionTracker()

        rev1 = tracker.next_revision("node-1")
        rev2 = tracker.next_revision("node-1")
        rev3 = tracker.next_revision("node-1")

        # Only rev3 should apply
        assert tracker.should_apply("node-1", rev3) is True
        assert tracker.should_apply("node-1", rev1) is False
        assert tracker.should_apply("node-1", rev2) is False
        assert tracker.stale_dropped == 2

    def test_independent_nodes(self) -> None:
        tracker = RevisionTracker()

        rev_a = tracker.next_revision("node-a")
        rev_b = tracker.next_revision("node-b")

        assert tracker.should_apply("node-a", rev_a) is True
        assert tracker.should_apply("node-b", rev_b) is True
        assert tracker.stale_dropped == 0


# ---------------------------------------------------------------------------
# Supersede-aware queue pruning
# ---------------------------------------------------------------------------


class TestVCADConnectionSupersedeQueue:
    """Test eval queue with supersede pruning."""

    def test_basic_enqueue_dequeue(self) -> None:
        queue = EvalQueue(max_size=10)

        job = EvalJob(node_id="node-1", revision=1, source="test code")
        assert queue.enqueue(job) is True

        result = queue.get_next()
        assert result is not None
        assert result.node_id == "node-1"
        assert result.revision == 1

    def test_supersede_older_pending_jobs(self) -> None:
        """Enqueue multiple rapid pending updates for same node before worker starts.
        Verify only newest pending revision is evaluated; older pending jobs are skipped.
        """
        queue = EvalQueue(max_size=10)

        # Enqueue 3 rapid updates for same node
        queue.enqueue(EvalJob(node_id="node-1", revision=1, source="v1"))
        queue.enqueue(EvalJob(node_id="node-1", revision=2, source="v2"))
        queue.enqueue(EvalJob(node_id="node-1", revision=3, source="v3"))

        # First two should have been marked superseded
        assert queue.superseded_dropped_total == 2

        # get_next should skip superseded and return only rev 3
        job = queue.get_next()
        assert job is not None
        assert job.revision == 3
        assert queue.superseded_skipped_before_eval_total == 2

        # Queue should be empty
        assert queue.get_next() is None

    def test_supersede_only_same_node(self) -> None:
        """Supersede only affects jobs for the same node_id."""
        queue = EvalQueue(max_size=10)

        queue.enqueue(EvalJob(node_id="node-a", revision=1, source="a1"))
        queue.enqueue(EvalJob(node_id="node-b", revision=1, source="b1"))
        queue.enqueue(EvalJob(node_id="node-a", revision=2, source="a2"))

        # Only node-a rev 1 should be superseded
        assert queue.superseded_dropped_total == 1

        # Should get: node-b (pending, not superseded), then node-a rev 2
        job1 = queue.get_next()
        assert job1 is not None
        # First non-superseded: skip node-a rev1 (superseded), get node-b rev1
        assert job1.node_id == "node-b"
        assert queue.superseded_skipped_before_eval_total == 1

        job2 = queue.get_next()
        assert job2 is not None
        assert job2.node_id == "node-a"
        assert job2.revision == 2

    def test_queue_bounded(self) -> None:
        queue = EvalQueue(max_size=3)

        assert queue.enqueue(EvalJob(node_id="n1", revision=1, source="s1")) is True
        assert queue.enqueue(EvalJob(node_id="n2", revision=1, source="s2")) is True
        assert queue.enqueue(EvalJob(node_id="n3", revision=1, source="s3")) is True
        assert queue.enqueue(EvalJob(node_id="n4", revision=1, source="s4")) is False

    def test_pending_count(self) -> None:
        queue = EvalQueue(max_size=10)

        queue.enqueue(EvalJob(node_id="node-1", revision=1, source="v1"))
        queue.enqueue(EvalJob(node_id="node-1", revision=2, source="v2"))
        queue.enqueue(EvalJob(node_id="node-2", revision=1, source="v1"))

        # node-1 rev1 is superseded, so 2 pending
        assert queue.pending_count() == 2

    def test_counters(self) -> None:
        """Verify both supersede counters are tracked correctly."""
        queue = EvalQueue(max_size=20)

        # Rapid updates: 5 versions for same node
        for rev in range(1, 6):
            queue.enqueue(EvalJob(node_id="node-x", revision=rev, source=f"v{rev}"))

        # 4 older jobs were marked superseded on enqueue
        assert queue.superseded_dropped_total == 4

        # Worker processes queue — 4 superseded jobs skipped, 1 evaluated
        job = queue.get_next()
        assert job is not None
        assert job.revision == 5
        assert queue.superseded_skipped_before_eval_total == 4

        assert queue.get_next() is None


# ---------------------------------------------------------------------------
# Trigger coalescing
# ---------------------------------------------------------------------------


class TestVCADConnectionTriggerCoalescing:
    """Test trigger coalescing window for event merging."""

    def test_events_within_window_merged(self) -> None:
        """Emit rapid events within coalesce window.
        Verify one merged cascade run for union of affected nodes.
        """
        cascades: list[set[str]] = []
        event = threading.Event()

        def on_cascade(nodes: set[str]) -> None:
            cascades.append(nodes)
            event.set()

        coalescer = TriggerCoalescer(coalesce_ms=50.0, callback=on_cascade)

        # Emit rapid events for multiple nodes
        coalescer.trigger("node-1", "fs-watch")
        coalescer.trigger("node-2", "mod-track")
        coalescer.trigger("node-3", "su-observer")

        # Wait for coalescing window to fire
        event.wait(timeout=2.0)

        assert len(cascades) == 1
        assert cascades[0] == {"node-1", "node-2", "node-3"}
        coalescer.cancel()

    def test_events_during_cascade_deferred(self) -> None:
        """Events during active cascade are deferred to next batch."""
        cascades: list[set[str]] = []
        cascade_events: list[threading.Event] = [threading.Event(), threading.Event()]
        cascade_index = [0]
        proceed_event = threading.Event()

        def on_cascade(nodes: set[str]) -> None:
            idx = cascade_index[0]
            cascades.append(nodes)
            if idx == 0:
                cascade_events[0].set()
                # Block first cascade to allow deferred events
                proceed_event.wait(timeout=2.0)
            cascade_index[0] += 1
            if idx == 1:
                cascade_events[1].set()

        coalescer = TriggerCoalescer(coalesce_ms=30.0, callback=on_cascade)

        # Trigger first batch
        coalescer.trigger("node-1", "fs-watch")

        # Wait for first cascade to start
        cascade_events[0].wait(timeout=2.0)

        # Now emit events while cascade is active — should be deferred
        coalescer.trigger("node-2", "manual")
        coalescer.trigger("node-3", "manual")

        # Let first cascade complete
        proceed_event.set()

        # Wait for deferred cascade
        cascade_events[1].wait(timeout=2.0)

        assert len(cascades) == 2
        assert cascades[0] == {"node-1"}
        assert cascades[1] == {"node-2", "node-3"}
        coalescer.cancel()

    def test_no_parallel_cascades(self) -> None:
        """Verify no parallel cascades execute."""
        active_count = [0]
        max_active = [0]
        lock = threading.Lock()
        done_event = threading.Event()

        def on_cascade(nodes: set[str]) -> None:
            with lock:
                active_count[0] += 1
                max_active[0] = max(max_active[0], active_count[0])
            time.sleep(0.05)
            with lock:
                active_count[0] -= 1
            done_event.set()

        coalescer = TriggerCoalescer(coalesce_ms=20.0, callback=on_cascade)

        coalescer.trigger("node-1", "fs-watch")
        done_event.wait(timeout=2.0)

        assert max_active[0] == 1
        coalescer.cancel()

    def test_duplicate_events_deduplicated(self) -> None:
        """Same node triggered multiple times within window produces one entry."""
        cascades: list[set[str]] = []
        event = threading.Event()

        def on_cascade(nodes: set[str]) -> None:
            cascades.append(nodes)
            event.set()

        coalescer = TriggerCoalescer(coalesce_ms=50.0, callback=on_cascade)

        coalescer.trigger("node-1", "fs-watch")
        coalescer.trigger("node-1", "mod-track")
        coalescer.trigger("node-1", "su-observer")

        event.wait(timeout=2.0)

        assert len(cascades) == 1
        assert cascades[0] == {"node-1"}
        coalescer.cancel()


# ---------------------------------------------------------------------------
# Persistent state
# ---------------------------------------------------------------------------


class TestVCADConnectionPersistentState:
    """Test persistent vcad runtime state management."""

    def test_save_and_load(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(
            node_id="node-1",
            source_file="/test/bracket.cmp.oo",
            revision=5,
            applied_revision=5,
            last_entity_id="ent-123",
            status="active",
        ))
        state.set_node(NodeState(
            node_id="node-2",
            source_file="/test/plate.cmp.oo",
            revision=3,
            applied_revision=2,
            status="active",
        ))

        state.save()
        assert os.path.exists(tmp_state_path)

        # Load into fresh instance
        loaded = VCADPersistentState(state_path=tmp_state_path)
        assert loaded.load() is True

        nodes = loaded.all_nodes()
        assert len(nodes) == 2
        assert nodes["node-1"].source_file == "/test/bracket.cmp.oo"
        assert nodes["node-1"].revision == 5
        assert nodes["node-2"].applied_revision == 2

    def test_load_missing_file(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        assert state.load() is False

    def test_atomic_write(self, tmp_state_path: str) -> None:
        """Verify save uses atomic write (no partial state on crash)."""
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(node_id="n1", source_file="/a.cmp.oo"))
        state.save()

        # File should be valid JSON
        with open(tmp_state_path) as f:
            data = json.load(f)
        assert "nodes" in data
        assert "n1" in data["nodes"]

    def test_remove_node(self, tmp_state_path: str) -> None:
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(node_id="n1", source_file="/a.cmp.oo"))
        state.set_node(NodeState(node_id="n2", source_file="/b.cmp.oo"))

        state.remove_node("n1")

        nodes = state.all_nodes()
        assert "n1" not in nodes
        assert "n2" in nodes


# ---------------------------------------------------------------------------
# Startup recovery and reconciliation
# ---------------------------------------------------------------------------


class TestVCADConnectionRecovery:
    """Test startup recovery and state reconciliation."""

    def test_no_drift(self) -> None:
        """No drift produces ok status."""
        persisted = {
            "node-1": NodeState(
                node_id="node-1",
                source_file=__file__,  # existing file
                revision=3,
                applied_revision=3,
            ),
        }
        runtime = [{"node_id": "node-1"}]

        drift = VCADReconciler.classify_drift(persisted, runtime)
        assert len(drift) == 0

        result = VCADReconciler.reconcile(
            VCADPersistentState(state_path="/dev/null"), drift
        )
        assert result["status"] == "ok"

    def test_missing_node_drift(self) -> None:
        """Persisted node absent in SketchUp."""
        persisted = {
            "node-1": NodeState(
                node_id="node-1", source_file=__file__, revision=1, applied_revision=1
            ),
        }
        runtime: list[dict] = []

        drift = VCADReconciler.classify_drift(persisted, runtime)
        assert len(drift) == 1
        assert drift[0].drift_type == "missing_node"

    def test_orphan_definition_drift(self) -> None:
        """SketchUp vcad definition absent in persisted state."""
        persisted: dict[str, NodeState] = {}
        runtime = [{"node_id": "orphan-1"}]

        drift = VCADReconciler.classify_drift(persisted, runtime)
        assert len(drift) == 1
        assert drift[0].drift_type == "orphan_definition"

    def test_source_missing_marks_degraded(self, tmp_state_path: str) -> None:
        """Remove a source file and verify node is marked degraded."""
        # Create a temp file then delete it to simulate missing source
        with tempfile.NamedTemporaryFile(suffix=".cmp.oo", delete=False) as f:
            missing_path = f.name
        os.unlink(missing_path)

        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(
            node_id="node-1",
            source_file=missing_path,
            revision=2,
            applied_revision=2,
            status="active",
        ))

        persisted = state.all_nodes()
        runtime = [{"node_id": "node-1"}]

        drift = VCADReconciler.classify_drift(persisted, runtime)
        assert any(d.drift_type == "source_missing" for d in drift)

        result = VCADReconciler.reconcile(state, drift)
        assert result["status"] == "degraded"

        # Verify node was marked degraded
        node = state.get_node("node-1")
        assert node is not None
        assert node.status == "degraded"

        # Check error code in actions
        degraded_actions = [
            a for a in result["actions"] if a["action"] == "mark_degraded"
        ]
        assert len(degraded_actions) == 1
        assert degraded_actions[0]["error_code"] == "SOURCE_FILE_MISSING"

    def test_revision_gap_drift(self) -> None:
        """applied_revision behind revision triggers cascade_update."""
        persisted = {
            "node-1": NodeState(
                node_id="node-1",
                source_file=__file__,
                revision=5,
                applied_revision=3,
            ),
        }
        runtime = [{"node_id": "node-1"}]

        drift = VCADReconciler.classify_drift(persisted, runtime)
        assert len(drift) == 1
        assert drift[0].drift_type == "revision_gap"

    def test_rebuild_revisions_from_state(self, tmp_state_path: str) -> None:
        """Rebuild revision counters from persisted state after restart."""
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(
            node_id="node-1",
            source_file="/test/a.cmp.oo",
            revision=7,
            applied_revision=7,
        ))
        state.set_node(NodeState(
            node_id="node-2",
            source_file="/test/b.cmp.oo",
            revision=3,
            applied_revision=3,
        ))
        state.save()

        # Simulate restart — load state and rebuild tracker
        loaded_state = VCADPersistentState(state_path=tmp_state_path)
        loaded_state.load()

        tracker = RevisionTracker()
        VCADReconciler.rebuild_revisions(loaded_state, tracker)

        assert tracker.current_revision("node-1") == 7
        assert tracker.current_revision("node-2") == 3

        # New revision should continue from restored value
        next_rev = tracker.next_revision("node-1")
        assert next_rev == 8

    def test_full_reconciliation_flow(self, tmp_state_path: str) -> None:
        """Full startup recovery: load state, classify drift, reconcile."""
        # Set up persisted state
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(
            node_id="node-1",
            source_file=__file__,  # exists
            revision=5,
            applied_revision=5,
        ))
        state.set_node(NodeState(
            node_id="node-2",
            source_file="/nonexistent/missing.cmp.oo",
            revision=3,
            applied_revision=3,
        ))
        state.save()

        # Simulate restart — load persisted state
        loaded = VCADPersistentState(state_path=tmp_state_path)
        loaded.load()

        # SketchUp bridge returns node-1, node-2, and an orphan node-3
        # (node-2 is present in SU but its source file is missing on disk)
        runtime_nodes = [
            {"node_id": "node-1"},
            {"node_id": "node-2"},
            {"node_id": "node-3"},
        ]

        drift = VCADReconciler.classify_drift(loaded.all_nodes(), runtime_nodes)

        # Should have: source_missing for node-2, orphan for node-3
        drift_types = {d.drift_type for d in drift}
        assert "source_missing" in drift_types
        assert "orphan_definition" in drift_types

        result = VCADReconciler.reconcile(loaded, drift)
        assert result["status"] == "degraded"

        # Rebuild tracker
        tracker = RevisionTracker()
        VCADReconciler.rebuild_revisions(loaded, tracker)

        # node-1 should still be at revision 5
        assert tracker.current_revision("node-1") == 5
        # node-3 (orphan) was added with revision 0
        assert tracker.current_revision("node-3") == 0


# ---------------------------------------------------------------------------
# Sidecar restart under load
# ---------------------------------------------------------------------------


class TestVCADConnectionSidecarRestart:
    """Test sidecar restart behavior under load."""

    def test_stale_guard_prevents_rollback_on_restart(self) -> None:
        """Restart sidecar during queued evals.
        Verify driver avoids stale rollback.
        """
        tracker = RevisionTracker()
        queue = EvalQueue(max_size=10)

        # Simulate pre-restart state: node-1 at revision 3
        tracker.set_revision("node-1", 3)

        # Queue some evals (representing pre-restart pending work)
        queue.enqueue(EvalJob(node_id="node-1", revision=2, source="old"))
        queue.enqueue(EvalJob(node_id="node-1", revision=3, source="current"))

        # Simulate sidecar restart: bump revision for cache rebuild
        new_rev = tracker.next_revision("node-1")  # now 4
        queue.enqueue(EvalJob(node_id="node-1", revision=new_rev, source="rebuilt"))

        # Process queue: only rev 4 should be executed
        executed = []
        while True:
            job = queue.get_next()
            if job is None:
                break
            executed.append(job)

        # Only the rebuilt job (rev 4) should be non-superseded
        assert len(executed) == 1
        assert executed[0].revision == new_rev

        # Old results (rev 2, 3) would be stale if they arrived
        assert tracker.should_apply("node-1", 2) is False
        assert tracker.should_apply("node-1", 3) is False
        assert tracker.should_apply("node-1", 4) is True
        assert tracker.stale_dropped == 2

    def test_topological_cascade_on_reconnect(self, tmp_state_path: str) -> None:
        """After sidecar restart, rebuild caches via topological cascade."""
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(
            node_id="node-a",
            source_file=__file__,
            revision=5,
            applied_revision=5,
        ))
        state.set_node(NodeState(
            node_id="node-b",
            source_file=__file__,
            revision=3,
            applied_revision=3,
        ))
        state.save()

        # Simulate restart: load state and rebuild
        loaded = VCADPersistentState(state_path=tmp_state_path)
        loaded.load()

        tracker = RevisionTracker()
        VCADReconciler.rebuild_revisions(loaded, tracker)

        # Simulate cache rebuild cascade: bump revisions
        cascade_nodes = list(loaded.all_nodes().keys())
        cascade_revisions = {}
        for nid in cascade_nodes:
            cascade_revisions[nid] = tracker.next_revision(nid)

        # Verify each node got a new revision for rebuild
        assert cascade_revisions["node-a"] == 6
        assert cascade_revisions["node-b"] == 4

        # Old revisions should not apply
        assert tracker.should_apply("node-a", 5) is False
        assert tracker.should_apply("node-b", 3) is False
        # New revisions should apply
        assert tracker.should_apply("node-a", 6) is True
        assert tracker.should_apply("node-b", 4) is True


# ---------------------------------------------------------------------------
# VCADSidecar lifecycle
# ---------------------------------------------------------------------------


class TestVCADConnectionSidecarLifecycle:
    """Test VCADSidecar process lifecycle management."""

    def test_init_default_path(self) -> None:
        sidecar = VCADSidecar()
        # Should have resolved some path (or None if root not found)
        assert isinstance(sidecar.process, type(None))

    def test_init_custom_path(self) -> None:
        sidecar = VCADSidecar(sidecar_path="/custom/path/binary")
        assert sidecar.sidecar_path == "/custom/path/binary"

    def test_init_from_env(self) -> None:
        with patch.dict(os.environ, {"SUPEX_VCAD_SIDECAR_PATH": "/env/path/binary"}):
            sidecar = VCADSidecar()
            assert sidecar.sidecar_path == "/env/path/binary"

    def test_ensure_running_no_binary(self) -> None:
        """ensure_running is a no-op when binary doesn't exist."""
        sidecar = VCADSidecar(sidecar_path="/nonexistent/binary")
        sidecar.ensure_running()
        assert sidecar.process is None

    def test_stop_no_process(self) -> None:
        """stop is a no-op when no process is running."""
        sidecar = VCADSidecar(sidecar_path="/test")
        sidecar.stop()  # Should not raise


# ---------------------------------------------------------------------------
# Reconciler with DAG integration
# ---------------------------------------------------------------------------


class TestReconcilerWithDag:
    """Test VCADReconciler integration with VCADDag for startup recovery."""

    @pytest.fixture
    def tmp_state_path(self, tmp_path):
        return str(tmp_path / "vcad-state.json")

    def test_reconciler_seed_and_load(self, tmp_state_path: str) -> None:
        """Seed persisted vcad-state.json, restart driver, verify state loads."""
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(
            node_id="node-1",
            source_file=__file__,
            revision=5,
            applied_revision=5,
        ))
        state.set_node(NodeState(
            node_id="node-2",
            source_file=__file__,
            revision=3,
            applied_revision=3,
        ))
        state.save()

        # Simulate driver restart
        dag = VCADDag(
            state=VCADPersistentState(state_path=tmp_state_path),
            tracker=RevisionTracker(),
        )
        dag.load_persisted_state()

        assert "node-1" in dag.nodes
        assert "node-2" in dag.nodes
        assert dag.current_revision("node-1") == 5
        assert dag.current_revision("node-2") == 3

    def test_reconciler_drift_buckets(self, tmp_state_path: str) -> None:
        """Seed state, reconcile with list_vcad_nodes snapshot,
        verify all drift buckets are classified correctly.
        """
        # Create and delete a file for source_missing
        with tempfile.NamedTemporaryFile(suffix=".cmp.oo", delete=False) as f:
            missing_path = f.name
        os.unlink(missing_path)

        state = VCADPersistentState(state_path=tmp_state_path)
        # node-1: OK in both persisted and SketchUp
        state.set_node(NodeState(
            node_id="node-1",
            source_file=__file__,
            revision=3,
            applied_revision=3,
        ))
        # node-2: source file missing
        state.set_node(NodeState(
            node_id="node-2",
            source_file=missing_path,
            revision=2,
            applied_revision=2,
        ))
        # node-3: persisted but not in SketchUp (missing_node)
        state.set_node(NodeState(
            node_id="node-3",
            source_file=__file__,
            revision=1,
            applied_revision=1,
        ))
        # node-4: has revision gap
        state.set_node(NodeState(
            node_id="node-4",
            source_file=__file__,
            revision=7,
            applied_revision=4,
        ))
        state.save()

        dag = VCADDag(
            state=VCADPersistentState(state_path=tmp_state_path),
            tracker=RevisionTracker(),
        )
        dag.load_persisted_state()

        # SketchUp snapshot: has node-1, node-2, node-4, and orphan node-5
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

    def test_reconciler_source_missing_degraded(self, tmp_state_path: str) -> None:
        """Verify source_missing nodes are marked degraded and return
        SOURCE_FILE_MISSING deterministically.
        """
        with tempfile.NamedTemporaryFile(suffix=".cmp.oo", delete=False) as f:
            missing_path = f.name
        os.unlink(missing_path)

        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(
            node_id="node-1",
            source_file=missing_path,
            revision=2,
            applied_revision=2,
            status="active",
        ))
        state.save()

        su_nodes = [{"node_id": "node-1"}]

        # Run reconciliation 3 times
        for _ in range(3):
            dag = VCADDag(
                state=VCADPersistentState(state_path=tmp_state_path),
                tracker=RevisionTracker(),
            )
            dag.load_persisted_state()
            buckets = dag.reconcile_with_sketchup(su_nodes)

            assert "node-1" in buckets["source_missing"]
            assert dag.nodes["node-1"].status == "degraded"

    def test_reconciler_cascade_after_reconcile(self, tmp_state_path: str) -> None:
        """After reconciliation, revision_gap nodes get cascade_update action,
        and revisions are properly rebuilt for subsequent operations.
        """
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(
            node_id="node-1",
            source_file=__file__,
            revision=5,
            applied_revision=3,  # gap: needs cascade
        ))
        state.save()

        dag = VCADDag(
            state=VCADPersistentState(state_path=tmp_state_path),
            tracker=RevisionTracker(),
        )
        dag.load_persisted_state()

        buckets = dag.reconcile_with_sketchup([{"node_id": "node-1"}])
        assert "node-1" in buckets["revision_gap"]

        # After reconcile, revision tracker should be at 5
        assert dag.current_revision("node-1") == 5

        # Bump should go to 6
        new_rev = dag.bump_revision("node-1")
        assert new_rev == 6

    def test_reconciler_orphan_tracked_in_dag(self, tmp_state_path: str) -> None:
        """Orphan definitions from SketchUp are added to the DAG."""
        state = VCADPersistentState(state_path=tmp_state_path)
        state.save()

        dag = VCADDag(
            state=VCADPersistentState(state_path=tmp_state_path),
            tracker=RevisionTracker(),
        )
        dag.load_persisted_state()

        su_nodes = [{"node_id": "orphan-1"}, {"node_id": "orphan-2"}]
        buckets = dag.reconcile_with_sketchup(su_nodes)

        assert set(buckets["orphan_definition"]) == {"orphan-1", "orphan-2"}
        assert "orphan-1" in dag.nodes
        assert dag.nodes["orphan-1"].status == "orphan"
        assert "orphan-2" in dag.nodes
        assert dag.nodes["orphan-2"].status == "orphan"

    def test_reconciler_missing_node_removed(self, tmp_state_path: str) -> None:
        """Nodes persisted but absent in SketchUp are removed from state."""
        state = VCADPersistentState(state_path=tmp_state_path)
        state.set_node(NodeState(
            node_id="gone-node",
            source_file=__file__,
            revision=1,
            applied_revision=1,
        ))
        state.save()

        dag = VCADDag(
            state=VCADPersistentState(state_path=tmp_state_path),
            tracker=RevisionTracker(),
        )
        dag.load_persisted_state()

        buckets = dag.reconcile_with_sketchup([])
        assert "gone-node" in buckets["missing_node"]

        # Should no longer be in DAG or persisted state
        assert dag.state.get_node("gone-node") is None


# ---------------------------------------------------------------------------
# VCADConnection — RPC lock and response ID validation
# ---------------------------------------------------------------------------


class TestVCADResponseIDValidation:
    """Test response ID matching in VCADConnection send_command."""

    def test_id_mismatch_raises_protocol_error(self, mock_sidecar: MockVCADSidecar) -> None:
        """Test that mismatched response ID raises VCADProtocolError."""
        # Override the mock sidecar to return wrong IDs
        original_create = mock_sidecar._create_response

        def bad_id_response(request):
            resp = original_create(request)
            if request.get("method") != "hello":
                resp["id"] = 999999  # Wrong ID
            return resp

        mock_sidecar._create_response = bad_id_response

        conn = VCADConnection(
            host="127.0.0.1",
            port=mock_sidecar.port,
            agent="test",
        )

        with pytest.raises(VCADProtocolError, match="Response ID mismatch"):
            conn.send_command("ping")

    def test_matching_id_succeeds(self, mock_sidecar: MockVCADSidecar) -> None:
        """Test that matching response ID succeeds normally."""
        conn = VCADConnection(
            host="127.0.0.1",
            port=mock_sidecar.port,
            agent="test",
        )
        result = conn.send_command("ping")
        assert result == {"status": "ok"}

    def test_connection_has_rpc_lock(self) -> None:
        """Test that VCADConnection has an RPC lock."""
        conn = VCADConnection(host="localhost", port=9877)
        assert hasattr(conn, "_rpc_lock")
        assert isinstance(conn._rpc_lock, type(threading.Lock()))


# ---------------------------------------------------------------------------
# get_vcad_connection — singleton rotation
# ---------------------------------------------------------------------------


class TestVCADSingletonRotation:
    """Test singleton connection rotation on endpoint change."""

    def setup_method(self) -> None:
        """Reset global singleton state before each test."""
        from supex_driver.connection import vcad_connection as vcmod

        self._vcmod = vcmod
        vcmod._vcad_connection = None
        vcmod._vcad_connection_identity = None

    def teardown_method(self) -> None:
        """Clean up global singleton state after each test."""
        vcmod = self._vcmod
        if vcmod._vcad_connection is not None:
            vcmod._vcad_connection.disconnect()
        vcmod._vcad_connection = None
        vcmod._vcad_connection_identity = None

    @patch("supex_driver.connection.vcad_sidecar.get_vcad_sidecar")
    def test_same_params_reuse_connection(self, mock_get_sidecar: Mock) -> None:
        """Test that same params return the same connection instance."""
        mock_get_sidecar.return_value = Mock()
        from supex_driver.connection.vcad_connection import get_vcad_connection

        conn1 = get_vcad_connection(host="localhost", port=9877, agent="test")
        conn2 = get_vcad_connection(host="localhost", port=9877, agent="test")
        assert conn1 is conn2

    @patch("supex_driver.connection.vcad_sidecar.get_vcad_sidecar")
    def test_different_port_rotates_connection(self, mock_get_sidecar: Mock) -> None:
        """Test that different port creates a new connection."""
        mock_get_sidecar.return_value = Mock()
        from supex_driver.connection.vcad_connection import get_vcad_connection

        conn1 = get_vcad_connection(host="localhost", port=9877, agent="test")
        conn2 = get_vcad_connection(host="localhost", port=9878, agent="test")
        assert conn1 is not conn2
        assert conn2.port == 9878

    @patch("supex_driver.connection.vcad_sidecar.get_vcad_sidecar")
    def test_different_agent_rotates_connection(self, mock_get_sidecar: Mock) -> None:
        """Test that different agent creates a new connection."""
        mock_get_sidecar.return_value = Mock()
        from supex_driver.connection.vcad_connection import get_vcad_connection

        conn1 = get_vcad_connection(host="localhost", port=9877, agent="user")
        conn2 = get_vcad_connection(host="localhost", port=9877, agent="mcp")
        assert conn1 is not conn2
        assert conn2.agent == "mcp"

    @patch("supex_driver.connection.vcad_sidecar.get_vcad_sidecar")
    @patch.dict(os.environ, {"SUPEX_WORKSPACE": "/project/a"})
    def test_different_workspace_rotates_connection(self, mock_get_sidecar: Mock) -> None:
        """Test that different workspace creates a new connection."""
        mock_get_sidecar.return_value = Mock()
        from supex_driver.connection.vcad_connection import get_vcad_connection

        conn1 = get_vcad_connection(host="localhost", port=9877, agent="test")
        with patch.dict(os.environ, {"SUPEX_WORKSPACE": "/project/b"}):
            conn2 = get_vcad_connection(host="localhost", port=9877, agent="test")
        assert conn1 is not conn2

    @patch("supex_driver.connection.vcad_sidecar.get_vcad_sidecar")
    def test_identity_includes_all_components(self, mock_get_sidecar: Mock) -> None:
        """Test that connection identity tracks all components."""
        mock_get_sidecar.return_value = Mock()
        from supex_driver.connection.vcad_connection import get_vcad_connection

        get_vcad_connection(host="myhost", port=1234, agent="myagent")
        identity = self._vcmod._vcad_connection_identity
        assert identity is not None
        assert identity[0] == "myagent"
        assert identity[1] == "myhost"
        assert identity[2] == 1234
