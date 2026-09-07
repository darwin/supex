"""MCP diagnostics tools for VCAD operational telemetry.

Exposes vcad_metrics and vcad_reconcile_status as MCP tools for telemetry
snapshots and reconciliation diagnostics.  VCAD health is exposed via the
unified ``check_status`` tool in ``mcp_server.py``; this module provides
the ``get_vcad_health_snapshot()`` helper consumed by that tool.
"""

import json
import logging
from typing import Any

from supex_driver.connection.vcad_metrics import get_vcad_metrics
from supex_driver.mcp.mcp_server import READ_ONLY, McpContext, mcp

logger = logging.getLogger("supex.mcp.vcad.diagnostics")


def get_vcad_health_snapshot() -> dict[str, Any]:
    """Return VCAD sidecar + viewer health as a plain dict.

    This is a helper consumed by ``check_status``; it is **not** an MCP tool.
    """
    sidecar: dict[str, Any] = {"status": "unknown"}
    viewer: dict[str, Any] = {"status": "unknown"}

    # Sidecar health
    try:
        from supex_driver.connection.vcad_connection import (
            _vcad_connection,
        )

        if _vcad_connection is not None and _vcad_connection.sock is not None:
            sidecar = {
                "status": "connected",
                "protocol_version": _vcad_connection._protocol_version,
                "capabilities": list(_vcad_connection._capabilities),
                "limits": dict(_vcad_connection._limits),
            }
        else:
            sidecar = {"status": "disconnected", "protocol_version": None}
    except Exception as e:
        sidecar = {"status": "error", "error": str(e)}

    # Viewer relay health
    try:
        from supex_driver.connection.vcad_viewer_relay import _relay

        if _relay is not None:
            if _relay.is_viewer_connected:
                viewer = {
                    "status": "connected",
                    "protocol_version": _relay.viewer_protocol_version,
                    "features": _relay.viewer_features,
                }
            else:
                viewer = {
                    "status": "disconnected",
                    "protocol_version": None,
                }
        else:
            viewer = {"status": "not_started", "protocol_version": None}
    except Exception as e:
        viewer = {"status": "error", "error": str(e)}

    return {"vcad_sidecar": sidecar, "vcad_viewer": viewer}


@mcp.tool(annotations=READ_ONLY)
def vcad_metrics(ctx: McpContext) -> str:
    """Return current telemetry snapshot (stable JSON schema).

    All metric names and units are part of the public contract.
    Counters are monotonic for one driver process lifetime.
    Gauges represent current state.

    Includes optional last_artifact_manifest when available, and
    manifest_read_errors for any manifests that failed to read.
    """
    metrics = get_vcad_metrics()
    snapshot = metrics.snapshot()

    # Attach last artifact manifest if available
    try:
        from supex_driver.connection.vcad_artifact_manifest import (
            get_artifact_store,
        )

        store = get_artifact_store()
        last_manifest = store.get_last_artifact_manifest()
        if last_manifest is not None:
            snapshot["last_artifact_manifest"] = last_manifest

        # Include any manifest read errors
        _manifests, read_errors = store.read_manifests_for_diagnostics()
        if read_errors:
            snapshot["manifest_read_errors"] = read_errors
    except Exception:
        pass

    return json.dumps(snapshot)


@mcp.tool(annotations=READ_ONLY)
def vcad_reconcile_status(ctx: McpContext) -> str:
    """Return last reconcile run: timestamp, drift summary, pending corrective actions.

    Reports the most recent reconciliation result including drift buckets,
    pending nodes requiring re-evaluation, and the overall outcome.
    """
    try:
        from supex_driver.connection.vcad_reconcile_state import (
            get_reconcile_state,
        )

        state = get_reconcile_state()
        return json.dumps(state.snapshot())
    except Exception as e:
        return json.dumps({
            "last_run_at": None,
            "drift": {},
            "pending_nodes": [],
            "last_outcome": "error",
            "error": str(e),
        })
