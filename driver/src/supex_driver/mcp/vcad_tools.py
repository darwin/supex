"""MCP tools for vcad BRep evaluation and SketchUp placement."""

import json
import logging
from typing import Any

from supex_driver.connection import (
    get_sketchup_connection,
    get_vcad_connection,
)
from supex_driver.connection.exceptions import (
    SketchUpConnectionError,
    SketchUpProtocolError,
    SketchUpRemoteError,
    SketchUpTimeoutError,
)
from supex_driver.connection.vcad_exceptions import (
    VcadCapabilityError,
    VcadConnectionError,
    VcadProtocolError,
    VcadRemoteError,
    VcadTimeoutError,
)
from supex_driver.mcp.server import McpContext, get_agent_name, mcp

logger = logging.getLogger("supex.mcp.vcad")


# ---------------------------------------------------------------------------
# Error handling helpers
# ---------------------------------------------------------------------------


def _handle_vcad_error(e: Exception, operation: str) -> str:
    """Standardized error handling for vcad sidecar errors.

    Preserves upstream error_code and details unchanged.
    Driver must not rewrite upstream error_code; it may only enrich
    missing details.operation.
    """
    if isinstance(e, VcadCapabilityError):
        logger.error(f"Capability error during {operation}: {e}")
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "error_code": e.error_code,
                "details": e.details,
            }
        )
    if isinstance(e, VcadProtocolError):
        logger.error(f"Protocol error during {operation}: {e}")
        response: dict[str, Any] = {
            "success": False,
            "error": str(e),
            "error_code": e.error_code,
        }
        if e.details:
            response["details"] = e.details
        return json.dumps(response)
    if isinstance(e, VcadRemoteError):
        logger.error(f"Remote error during {operation}: {e}")
        response = {
            "success": False,
            "error": e.message,
            "error_code": e.code,
        }
        if e.data:
            response["details"] = e.data
        return json.dumps(response)
    if isinstance(e, (VcadConnectionError, VcadTimeoutError)):
        logger.error(f"Connection error during {operation}: {e}")
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "error_type": "connection",
            }
        )
    logger.exception(f"Unexpected error during {operation}: {e}")
    return json.dumps(
        {
            "success": False,
            "error": str(e),
            "error_type": "unexpected",
        }
    )


def _handle_sketchup_error(e: Exception, operation: str) -> str:
    """Standardized error handling for SketchUp bridge errors."""
    if isinstance(e, SketchUpRemoteError):
        logger.error(f"Remote error during {operation}: {e}")
        return json.dumps(
            {
                "success": False,
                "error": e.message,
                "error_type": "remote",
                "error_code": e.code,
            }
        )
    if isinstance(e, (SketchUpConnectionError, SketchUpTimeoutError)):
        logger.error(f"Connection error during {operation}: {e}")
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "error_type": "connection",
            }
        )
    if isinstance(e, SketchUpProtocolError):
        logger.error(f"Protocol error during {operation}: {e}")
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "error_type": "protocol",
            }
        )
    logger.exception(f"Unexpected error during {operation}: {e}")
    return json.dumps(
        {
            "success": False,
            "error": str(e),
            "error_type": "unexpected",
        }
    )


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
def vcad_place(
    ctx: McpContext,
    node_id: str,
    source_file: str,
    position: list[float] | None = None,
    component_name: str | None = None,
) -> str:
    """Evaluate a .skp.oo file and place the resulting mesh in SketchUp.

    1. Send source file to vcad sidecar for evaluation -> OBJ file
    2. Send OBJ path to SketchUp -> definitions.import -> ComponentDefinition
    3. Store vcad metadata in attribute dictionary

    Args:
        ctx: MCP context
        node_id: Unique identifier for this vcad node
        source_file: Path to the .skp.oo file
        position: Optional [x, y, z] position in mm (default [0, 0, 0])
        component_name: Optional name for the SketchUp component
    """
    agent = get_agent_name(ctx)

    # Step 1: Evaluate source file via vcad sidecar
    try:
        vcad = get_vcad_connection(agent=agent)
        eval_result = vcad.eval_file(source_file)
    except (
        VcadCapabilityError,
        VcadProtocolError,
        VcadRemoteError,
        VcadConnectionError,
        VcadTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_place:eval")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_place:eval")

    obj_path = eval_result.get("obj_path")
    if not obj_path:
        return json.dumps(
            {
                "success": False,
                "error": "Sidecar did not return obj_path",
                "error_type": "unexpected",
            }
        )

    # Step 2: Place in SketchUp via Ruby bridge
    try:
        sketchup = get_sketchup_connection(agent=agent)
        place_params: dict[str, Any] = {
            "obj_path": obj_path,
            "node_id": node_id,
            "source_file": source_file,
        }
        if position is not None:
            place_params["position"] = position
        if component_name is not None:
            place_params["component_name"] = component_name

        result = sketchup.send_command(
            method="place_vcad_node",
            params=place_params,
            request_id=ctx.request_id,
        )
        return json.dumps(result)
    except (
        SketchUpRemoteError,
        SketchUpConnectionError,
        SketchUpTimeoutError,
        SketchUpProtocolError,
    ) as e:
        return _handle_sketchup_error(e, "vcad_place:import")
    except Exception as e:
        return _handle_sketchup_error(e, "vcad_place:import")


@mcp.tool()
def vcad_update(ctx: McpContext, node_id: str, source_file: str | None = None) -> str:
    """Re-evaluate vcad node and update SketchUp geometry.

    If source_file is not provided, queries SketchUp for the node's
    current source_file attribute.

    Args:
        ctx: MCP context
        node_id: The vcad node identifier to update
        source_file: Optional new source file path (uses existing if omitted)
    """
    agent = get_agent_name(ctx)

    # If source_file not given, look it up from SketchUp
    if source_file is None:
        try:
            sketchup = get_sketchup_connection(agent=agent)
            node_info = sketchup.send_command(
                method="get_vcad_node",
                params={"node_id": node_id},
                request_id=ctx.request_id,
            )
            source_file = node_info.get("source_file")
            if not source_file:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"No source_file found for node {node_id}",
                        "error_type": "remote",
                    }
                )
        except (
            SketchUpRemoteError,
            SketchUpConnectionError,
            SketchUpTimeoutError,
            SketchUpProtocolError,
        ) as e:
            return _handle_sketchup_error(e, "vcad_update:lookup")
        except Exception as e:
            return _handle_sketchup_error(e, "vcad_update:lookup")

    # Re-evaluate via sidecar
    try:
        vcad = get_vcad_connection(agent=agent)
        eval_result = vcad.eval_file(source_file)
    except (
        VcadCapabilityError,
        VcadProtocolError,
        VcadRemoteError,
        VcadConnectionError,
        VcadTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_update:eval")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_update:eval")

    obj_path = eval_result.get("obj_path")
    if not obj_path:
        return json.dumps(
            {
                "success": False,
                "error": "Sidecar did not return obj_path",
                "error_type": "unexpected",
            }
        )

    # Update in SketchUp via Ruby bridge
    try:
        sketchup = get_sketchup_connection(agent=agent)
        result = sketchup.send_command(
            method="update_vcad_node",
            params={
                "obj_path": obj_path,
                "node_id": node_id,
                "source_file": source_file,
            },
            request_id=ctx.request_id,
        )
        return json.dumps(result)
    except (
        SketchUpRemoteError,
        SketchUpConnectionError,
        SketchUpTimeoutError,
        SketchUpProtocolError,
    ) as e:
        return _handle_sketchup_error(e, "vcad_update:import")
    except Exception as e:
        return _handle_sketchup_error(e, "vcad_update:import")


@mcp.tool()
def vcad_inspect(ctx: McpContext, source: str) -> str:
    """Inspect vcad geometry: volume, surface area, bounding box.

    Source can be a .skp.oo file path or inline Loon code.

    Args:
        ctx: MCP context
        source: A .skp.oo file path or inline Loon code
    """
    try:
        vcad = get_vcad_connection(agent=get_agent_name(ctx))
        result = vcad.inspect(source)
        return json.dumps({"success": True, **result})
    except (
        VcadCapabilityError,
        VcadProtocolError,
        VcadRemoteError,
        VcadConnectionError,
        VcadTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_inspect")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_inspect")


@mcp.tool()
def vcad_export(
    ctx: McpContext,
    source: str,
    format: str = "obj",
    output_path: str = "",
) -> str:
    """Export vcad geometry to OBJ or STEP.

    Args:
        ctx: MCP context
        source: A .skp.oo file path or inline Loon code
        format: Export format - "obj" or "step" (default "obj")
        output_path: Optional output file path. Auto-generated if empty.
    """
    try:
        vcad = get_vcad_connection(agent=get_agent_name(ctx))
        params: dict[str, str] = {
            "source": source,
            "format": format,
        }
        if output_path:
            params["output_path"] = output_path
        result = vcad.send_command("vcad.export", params)
        return json.dumps({"success": True, **result})
    except (
        VcadCapabilityError,
        VcadProtocolError,
        VcadRemoteError,
        VcadConnectionError,
        VcadTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_export")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_export")


@mcp.tool()
def vcad_eval(ctx: McpContext, code: str) -> str:
    """Evaluate Loon code in vcad sidecar (REPL mode). Returns display string.

    Args:
        ctx: MCP context
        code: Loon source code to evaluate
    """
    try:
        vcad = get_vcad_connection(agent=get_agent_name(ctx))
        result = vcad.eval_code(code)
        return json.dumps({"success": True, **result})
    except (
        VcadCapabilityError,
        VcadProtocolError,
        VcadRemoteError,
        VcadConnectionError,
        VcadTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_eval")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_eval")


@mcp.tool()
def vcad_list_nodes(ctx: McpContext) -> str:
    """List all vcad nodes in the current SketchUp model."""
    try:
        sketchup = get_sketchup_connection(agent=get_agent_name(ctx))
        result = sketchup.send_command(
            method="list_vcad_nodes",
            params={},
            request_id=ctx.request_id,
        )
        return json.dumps(result)
    except (
        SketchUpRemoteError,
        SketchUpConnectionError,
        SketchUpTimeoutError,
        SketchUpProtocolError,
    ) as e:
        return _handle_sketchup_error(e, "vcad_list_nodes")
    except Exception as e:
        return _handle_sketchup_error(e, "vcad_list_nodes")
