"""Replay policy and expected-model guard of SketchupConnection.send_command.

A request whose bytes reached SketchUp but whose response never arrived has an
unknown outcome. Read-only tools may be sent again; anything else must surface
SketchUpUnknownResultError instead of being replayed.
"""

import json
import os
import time
from collections.abc import Iterable
from unittest.mock import Mock, patch

import pytest

from supex_driver.connection import sketchup_connection as connection_module
from supex_driver.connection.sketchup_connection import (
    SketchupConnection,
    resolve_expected_model,
)
from supex_driver.connection.sketchup_exceptions import (
    SketchUpConnectionError,
    SketchUpUnknownResultError,
)

REQUEST_ID = 42


def response_bytes(result: dict, request_id: int = REQUEST_ID) -> bytes:
    return json.dumps({"jsonrpc": "2.0", "result": result, "id": request_id}).encode() + b"\n"


def make_socket(reads: Iterable[bytes | BaseException]) -> Mock:
    """Socket whose health peek says "alive" and whose full reads follow ``reads``."""
    sock = Mock()
    queue = iter(reads)

    def recv(_size: int, *flags: int) -> bytes:
        if flags:  # MSG_PEEK health check in _is_connection_healthy
            raise BlockingIOError
        item = next(queue)
        if isinstance(item, BaseException):
            raise item
        return item

    sock.recv.side_effect = recv
    return sock


def connected(sock: Mock, **kwargs: object) -> SketchupConnection:
    conn = SketchupConnection(host="localhost", port=9876, agent="test", **kwargs)  # type: ignore[arg-type]
    conn.sock = sock
    conn._identified = True
    conn._last_activity = time.time()
    return conn


def reconnect_with(conn: SketchupConnection, sock: Mock) -> Mock:
    """Patch conn.connect so the retry path lands on ``sock``."""

    def connect() -> bool:
        conn.sock = sock
        conn._identified = True
        return True

    return Mock(side_effect=connect)


def sent_request(sock: Mock) -> dict:
    return json.loads(sock.sendall.call_args[0][0].decode().strip())


@pytest.fixture(autouse=True)
def _two_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connection_module, "MAX_RETRIES", 2)


class TestReplayPolicy:
    def test_mutation_is_not_replayed_after_timeout(self) -> None:
        first = make_socket([TimeoutError()])
        conn = connected(first)
        connect = reconnect_with(conn, make_socket([response_bytes({"success": True})]))

        with patch.object(conn, "connect", connect), pytest.raises(SketchUpUnknownResultError) as info:
            conn.send_command("eval_ruby", {"code": "x"}, request_id=REQUEST_ID)

        assert first.sendall.call_count == 1
        connect.assert_not_called()
        assert conn.sock is None, "connection with an in-flight request is dropped"
        assert "eval_ruby" in str(info.value)
        assert "inspect the model" in str(info.value)

    def test_unknown_result_is_a_connection_error_for_existing_handlers(self) -> None:
        conn = connected(make_socket([TimeoutError()]))

        with pytest.raises(SketchUpConnectionError):
            conn.send_command("eval_ruby_file", {"file_path": "a.rb"}, request_id=REQUEST_ID)

    def test_connection_reset_after_send_is_not_replayed(self) -> None:
        conn = connected(make_socket([ConnectionResetError("peer reset")]))
        connect = reconnect_with(conn, make_socket([response_bytes({"success": True})]))

        with patch.object(conn, "connect", connect), pytest.raises(SketchUpUnknownResultError):
            conn.send_command("save_model", {}, request_id=REQUEST_ID)

        connect.assert_not_called()

    def test_read_only_tool_is_replayed_after_timeout(self) -> None:
        first = make_socket([TimeoutError()])
        second = make_socket([response_bytes({"success": True, "title": "house"})])
        conn = connected(first)
        connect = reconnect_with(conn, second)

        with patch.object(conn, "connect", connect):
            result = conn.send_command("get_model_info", {}, request_id=REQUEST_ID)

        assert result["title"] == "house"
        assert first.sendall.call_count == 1
        assert second.sendall.call_count == 1
        connect.assert_called_once()

    def test_explicit_replay_safe_overrides_tool_policy(self) -> None:
        conn = connected(make_socket([TimeoutError()]))
        second = make_socket([response_bytes({"success": True})])
        connect = reconnect_with(conn, second)

        with patch.object(conn, "connect", connect):
            result = conn.send_command(
                "eval_ruby", {"code": "1"}, request_id=REQUEST_ID, replay_safe=True
            )

        assert result["success"] is True
        connect.assert_called_once()

    def test_failure_before_send_is_retried_for_mutation(self) -> None:
        first = make_socket([])
        first.sendall.side_effect = BrokenPipeError("pipe")
        second = make_socket([response_bytes({"success": True})])
        conn = connected(first)
        connect = reconnect_with(conn, second)

        with patch.object(conn, "connect", connect):
            result = conn.send_command("eval_ruby", {"code": "1"}, request_id=REQUEST_ID)

        assert result["success"] is True
        connect.assert_called_once()
        assert second.sendall.call_count == 1

    def test_read_only_tool_gives_up_after_max_retries(self) -> None:
        conn = connected(make_socket([TimeoutError()]))
        sockets = [make_socket([TimeoutError()]) for _ in range(2)]
        calls = iter(sockets)

        def connect() -> bool:
            conn.sock = next(calls)
            conn._identified = True
            return True

        with patch.object(conn, "connect", Mock(side_effect=connect)), pytest.raises(
            SketchUpConnectionError, match="after 3 attempts"
        ):
            conn.send_command("ping", {}, request_id=REQUEST_ID)

    def test_tools_call_form_uses_inner_tool_name_for_policy(self) -> None:
        conn = connected(make_socket([TimeoutError()]))
        connect = reconnect_with(conn, make_socket([response_bytes({"ok": True})]))
        params = {"name": "get_selection", "arguments": {}}

        with patch.object(conn, "connect", connect):
            result = conn.send_command("tools/call", params, request_id=REQUEST_ID)

        assert result == {"ok": True}
        connect.assert_called_once()


class TestTransportInfo:
    def test_reports_effective_policy(self) -> None:
        conn = SketchupConnection(timeout=7.5, expected_model="/models/house.skp")

        info = conn.transport_info()

        assert info == {
            "timeout_s": 7.5,
            "max_retries": 2,
            "replay_after_send": "read_only_tools_only",
            "expected_model": "/models/house.skp",
        }


class TestExpectedModelResolution:
    def test_unset_gives_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SUPEX_EXPECTED_MODEL", raising=False)

        assert resolve_expected_model() is None
        assert resolve_expected_model("") is None

    def test_relative_env_value_resolves_against_workspace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SUPEX_WORKSPACE", "/work/nextgen")
        monkeypatch.setenv("SUPEX_EXPECTED_MODEL", "../citadela-model/citadela.skp")

        assert resolve_expected_model() == "/work/citadela-model/citadela.skp"

    def test_absolute_value_is_normalized(self) -> None:
        assert resolve_expected_model("/models//house/./a.skp") == "/models/house/a.skp"

    def test_explicit_value_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPEX_EXPECTED_MODEL", "/env/model.skp")

        assert resolve_expected_model("/explicit.skp", workspace="/w") == "/explicit.skp"

    def test_connection_reads_env_at_creation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPEX_WORKSPACE", "/work")
        monkeypatch.setenv("SUPEX_EXPECTED_MODEL", "house.skp")

        assert SketchupConnection().expected_model == "/work/house.skp"


class TestExpectedModelInjection:
    EXPECTED = "/models/house.skp"

    def send(self, method: str, params: dict | None) -> dict:
        sock = make_socket([response_bytes({"success": True})])
        conn = connected(sock, expected_model=self.EXPECTED)
        conn.send_command(method, params, request_id=REQUEST_ID)
        return sent_request(sock)

    def test_model_bound_tool_gets_guard_argument(self) -> None:
        request = self.send("eval_ruby", {"code": "1"})

        assert request["params"]["arguments"] == {
            "code": "1",
            "expected_model_path": self.EXPECTED,
        }

    def test_tools_call_form_gets_guard_argument(self) -> None:
        request = self.send("tools/call", {"name": "save_model", "arguments": {"path": "a.skp"}})

        assert request["params"]["arguments"]["expected_model_path"] == self.EXPECTED

    def test_explicit_argument_is_kept(self) -> None:
        request = self.send("eval_ruby", {"code": "1", "expected_model_path": "/other.skp"})

        assert request["params"]["arguments"]["expected_model_path"] == "/other.skp"

    @pytest.mark.parametrize("tool", ["ping", "open_model", "console_capture_status"])
    def test_exempt_tools_are_not_guarded(self, tool: str) -> None:
        request = self.send(tool, {"path": "/models/house.skp"} if tool == "open_model" else {})

        assert "expected_model_path" not in request["params"]["arguments"]

    def test_direct_jsonrpc_method_is_untouched(self) -> None:
        request = self.send("resources/list", {})

        assert request["method"] == "resources/list"
        assert request["params"] == {}

    def test_no_injection_without_expected_model(self) -> None:
        sock = make_socket([response_bytes({"success": True})])
        conn = connected(sock, expected_model=None)
        conn.send_command("eval_ruby", {"code": "1"}, request_id=REQUEST_ID)

        assert sent_request(sock)["params"]["arguments"] == {"code": "1"}


class TestSingletonRotation:
    def setup_method(self) -> None:
        connection_module._sketchup_connection = None
        connection_module._connection_identity = None

    def teardown_method(self) -> None:
        if connection_module._sketchup_connection is not None:
            connection_module._sketchup_connection.disconnect()
        connection_module._sketchup_connection = None
        connection_module._connection_identity = None

    def test_expected_model_change_rotates_connection(self) -> None:
        with patch.dict(os.environ, {"SUPEX_EXPECTED_MODEL": "/a.skp"}):
            conn1 = connection_module.get_sketchup_connection(agent="test")
        with patch.dict(os.environ, {"SUPEX_EXPECTED_MODEL": "/b.skp"}):
            conn2 = connection_module.get_sketchup_connection(agent="test")

        assert conn1 is not conn2
        assert conn2.expected_model == "/b.skp"
