"""E2E tests for VCAD data imports using mock sidecar.

Tests the extract_imports and eval_with_imports JSON-RPC methods
over real TCP connections to MockVCADSidecar.
"""

import json
import os

import pytest

from supex_driver.connection.vcad_connection import VCADConnection
from supex_driver.connection.vcad_exceptions import VCADRemoteError
from tests.helpers.mock_vcad_sidecar import MockVCADSidecar


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


# ---------------------------------------------------------------------------
# extract_imports
# ---------------------------------------------------------------------------


class TestDataImportsExtract:
    """Test vcad.extract_imports via mock sidecar."""

    def test_extract_imports_success(self, mock_sidecar):
        """extract_imports returns imports and transformed_source."""
        mock_sidecar.set_response(
            "tools/call",
            result={
                "imports": [
                    {
                        "import_id": "import_0",
                        "binding_name": "host-dims",
                        "extracts": ["dims"],
                        "source": "host",
                        "selector": "entity:12345",
                        "injected_symbol": "__vcad_import_0",
                    }
                ],
                "transformed_source": "[let host-dims __vcad_import_0]\n[cube 10.0 10.0 10.0]",
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        result = conn.extract_imports(
            '[let host-dims [import :host "entity:12345" :dims]]\n[cube 10.0 10.0 10.0]'
        )

        assert "imports" in result
        assert len(result["imports"]) == 1
        assert result["imports"][0]["binding_name"] == "host-dims"
        assert result["imports"][0]["extracts"] == ["dims"]
        assert result["imports"][0]["selector"] == "entity:12345"
        assert "__vcad_import_0" in result["transformed_source"]
        conn.disconnect()

    def test_extract_imports_no_imports(self, mock_sidecar):
        """Source without imports returns empty imports list."""
        mock_sidecar.set_response(
            "tools/call",
            result={
                "imports": [],
                "transformed_source": "[cube 10.0 10.0 10.0]",
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        result = conn.extract_imports("[cube 10.0 10.0 10.0]")

        assert result["imports"] == []
        assert result["transformed_source"] == "[cube 10.0 10.0 10.0]"
        conn.disconnect()

    def test_extract_imports_invalid_form(self, mock_sidecar):
        """Invalid import form returns IMPORT_FORM_INVALID error."""
        mock_sidecar.set_response(
            "tools/call",
            error={
                "code": -32000,
                "message": "IMPORT_FORM_INVALID: unsupported extract type :color",
                "data": {"error_code": "IMPORT_FORM_INVALID"},
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        with pytest.raises(VCADRemoteError) as exc_info:
            conn.extract_imports('[let x [import :host "entity:1" :color]]')

        assert exc_info.value.code == -32000
        assert exc_info.value.data.get("error_code") == "IMPORT_FORM_INVALID"
        conn.disconnect()

    def test_extract_imports_multiple(self, mock_sidecar):
        """Multiple imports extracted correctly."""
        mock_sidecar.set_response(
            "tools/call",
            result={
                "imports": [
                    {
                        "import_id": "import_0",
                        "binding_name": "dims",
                        "extracts": ["dims"],
                        "source": "host",
                        "selector": "entity:100",
                        "injected_symbol": "__vcad_import_0",
                    },
                    {
                        "import_id": "import_1",
                        "binding_name": "bb",
                        "extracts": ["bbox"],
                        "source": "host",
                        "selector": "entity:200",
                        "injected_symbol": "__vcad_import_1",
                    },
                ],
                "transformed_source": "[let dims __vcad_import_0]\n[let bb __vcad_import_1]",
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        result = conn.extract_imports(
            '[let dims [import :host "entity:100" :dims]]\n'
            '[let bb [import :host "entity:200" :bbox]]'
        )

        assert len(result["imports"]) == 2
        assert result["imports"][0]["extracts"] == ["dims"]
        assert result["imports"][1]["extracts"] == ["bbox"]
        conn.disconnect()


# ---------------------------------------------------------------------------
# eval_with_imports
# ---------------------------------------------------------------------------


class TestDataImportsEval:
    """Test vcad.eval_with_imports via mock sidecar."""

    def test_eval_with_imports_success(self, mock_sidecar, tmp_path):
        """eval_with_imports evaluates source with injected data."""
        obj_path = str(tmp_path / "result.dae")
        mock_sidecar.set_response(
            "tools/call",
            result={
                "obj_path": obj_path,
                "volume": 1000.0,
                "surface_area": 600.0,
                "is_empty": False,
                "bbox": {"min": [0, 0, 0], "max": [10, 10, 10]},
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        result = conn.eval_with_imports(
            transformed_source="[let dims __vcad_import_0]\n[cube 10.0 10.0 10.0]",
            base_dir=str(tmp_path),
            imports={
                "import_0": {
                    "extract": "dims",
                    "injected_symbol": "__vcad_import_0",
                    "data": {"width": 100.0, "height": 200.0, "depth": 50.0},
                }
            },
        )

        assert result["volume"] == 1000.0
        assert result["obj_path"] == obj_path
        conn.disconnect()

    def test_eval_with_imports_no_imports(self, mock_sidecar, tmp_path):
        """eval_with_imports works with empty imports."""
        mock_sidecar.set_response(
            "tools/call",
            result={
                "obj_path": str(tmp_path / "result.dae"),
                "volume": 500.0,
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        result = conn.eval_with_imports(
            transformed_source="[cube 5.0 10.0 10.0]",
            imports={},
        )

        assert result["volume"] == 500.0
        conn.disconnect()

    def test_eval_with_imports_error(self, mock_sidecar):
        """eval_with_imports error propagated."""
        mock_sidecar.set_response(
            "tools/call",
            error={
                "code": -32000,
                "message": "Loon evaluation error: undefined binding __vcad_import_0",
                "data": {"error_code": "LOON_ERROR"},
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        with pytest.raises(VCADRemoteError) as exc_info:
            conn.eval_with_imports(
                transformed_source="[let x __vcad_import_0]",
                imports={},
            )

        assert exc_info.value.code == -32000
        assert exc_info.value.data.get("error_code") == "LOON_ERROR"
        conn.disconnect()


# ---------------------------------------------------------------------------
# Full import flow (extract -> resolve mock -> eval)
# ---------------------------------------------------------------------------


class TestDataImportsFullFlow:
    """Test the complete import resolution flow."""

    def test_full_flow_dimensions(self, mock_sidecar, tmp_path):
        """Complete flow: extract -> resolve (mocked) -> eval."""
        # Step 1: extract_imports response
        extract_response = {
            "imports": [
                {
                    "import_id": "import_0",
                    "binding_name": "host-dims",
                    "extracts": ["dims"],
                    "source": "host",
                    "selector": "entity:42",
                    "injected_symbol": "__vcad_import_0",
                }
            ],
            "transformed_source": "[let host-dims __vcad_import_0]\n[cube 10.0 10.0 10.0]",
        }

        # Step 2: eval_with_imports response
        eval_response = {
            "obj_path": str(tmp_path / "output.dae"),
            "volume": 1000.0,
            "surface_area": 600.0,
            "is_empty": False,
        }

        # Alternate responses per call
        call_count = [0]
        original_create = mock_sidecar._create_response

        def custom_response(request):
            method = request.get("method", "")
            if method == "tools/call":
                call_count[0] += 1
                if call_count[0] == 1:
                    return {
                        "jsonrpc": "2.0",
                        "result": extract_response,
                        "id": request.get("id"),
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "result": eval_response,
                        "id": request.get("id"),
                    }
            return original_create(request)

        mock_sidecar._create_response = custom_response

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")

        # Extract imports
        extraction = conn.extract_imports(
            '[let host-dims [import :host "entity:42" :dims]]\n[cube 10.0 10.0 10.0]'
        )
        assert len(extraction["imports"]) == 1

        # Simulate resolve (SketchUp would do this)
        resolved = {
            "import_0": {
                "extract": "dims",
                "injected_symbol": "__vcad_import_0",
                "data": {"width": 100.0, "height": 200.0, "depth": 50.0},
            }
        }

        # Eval with imports
        result = conn.eval_with_imports(
            transformed_source=extraction["transformed_source"],
            base_dir=str(tmp_path),
            imports=resolved,
        )

        assert result["volume"] == 1000.0
        conn.disconnect()

    def test_full_flow_bbox_and_transform(self, mock_sidecar, tmp_path):
        """Multiple extract types in one flow."""
        mock_sidecar.set_response(
            "tools/call",
            result={
                "imports": [
                    {
                        "import_id": "import_0",
                        "binding_name": "bb",
                        "extracts": ["bbox"],
                        "source": "host",
                        "selector": "entity:10",
                        "injected_symbol": "__vcad_import_0",
                    },
                    {
                        "import_id": "import_1",
                        "binding_name": "tr",
                        "extracts": ["transform"],
                        "source": "host",
                        "selector": "entity:20",
                        "injected_symbol": "__vcad_import_1",
                    },
                ],
                "transformed_source": "[let bb __vcad_import_0]\n[let tr __vcad_import_1]",
            },
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        result = conn.extract_imports(
            '[let bb [import :host "entity:10" :bbox]]\n'
            '[let tr [import :host "entity:20" :transform]]'
        )

        assert len(result["imports"]) == 2
        extracts = set()
        for imp in result["imports"]:
            extracts.update(imp["extracts"])
        assert extracts == {"bbox", "transform"}
        conn.disconnect()


# ---------------------------------------------------------------------------
# Connection convenience methods
# ---------------------------------------------------------------------------


class TestVCADConnectionImportMethods:
    """Test VCADConnection convenience methods for imports."""

    def test_extract_imports_method(self, mock_sidecar):
        """extract_imports sends correct JSON-RPC request."""
        mock_sidecar.set_response(
            "tools/call",
            result={"imports": [], "transformed_source": "[cube 1.0 1.0 1.0]"},
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        conn.extract_imports("[cube 1.0 1.0 1.0]")

        # Verify the request was sent correctly
        tools_calls = [
            r
            for r in mock_sidecar.requests
            if r.get("method") == "tools/call"
        ]
        assert len(tools_calls) == 1
        params = tools_calls[0]["params"]
        assert params["name"] == "vcad.extract_imports"
        assert params["arguments"]["source"] == "[cube 1.0 1.0 1.0]"
        conn.disconnect()

    def test_eval_with_imports_method(self, mock_sidecar):
        """eval_with_imports sends correct JSON-RPC request."""
        mock_sidecar.set_response(
            "tools/call",
            result={"obj_path": "/tmp/out.dae", "volume": 100.0},
        )

        conn = VCADConnection(host="127.0.0.1", port=mock_sidecar.port, agent="e2e")
        conn.eval_with_imports(
            transformed_source="[cube 1.0 1.0 1.0]",
            base_dir="/project",
            imports={
                "import_0": {
                    "extract": "dims",
                    "injected_symbol": "__vcad_import_0",
                    "data": {"width": 10.0},
                }
            },
        )

        tools_calls = [
            r
            for r in mock_sidecar.requests
            if r.get("method") == "tools/call"
        ]
        assert len(tools_calls) == 1
        params = tools_calls[0]["params"]
        assert params["name"] == "vcad.eval_with_imports"
        args = params["arguments"]
        assert args["transformed_source"] == "[cube 1.0 1.0 1.0]"
        assert args["base_dir"] == "/project"
        assert "import_0" in args["imports"]
        conn.disconnect()
