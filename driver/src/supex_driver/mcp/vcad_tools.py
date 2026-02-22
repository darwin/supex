"""MCP tools for VCAD BRep evaluation and SketchUp placement."""

import json
import logging
import os
from typing import Any

from supex_driver.connection import (
    get_sketchup_connection,
    get_vcad_connection,
)
from supex_driver.connection.vcad_dag import ImportRef, VcadDag, VcadNode
from supex_driver.connection.sketchup_exceptions import (
    SketchUpConnectionError,
    SketchUpProtocolError,
    SketchUpRemoteError,
    SketchUpTimeoutError,
)
from supex_driver.connection.vcad_exceptions import (
    VCADCapabilityError,
    VCADConnectionError,
    VCADProtocolError,
    VCADRemoteError,
    VCADTimeoutError,
)
from supex_driver.mcp.mcp_server import McpContext, get_agent_name, mcp

logger = logging.getLogger("supex.mcp.vcad")

# ---------------------------------------------------------------------------
# DAG singleton
# ---------------------------------------------------------------------------

_vcad_dag: VcadDag | None = None


def get_vcad_dag() -> VcadDag:
    """Get or create the global VCAD DAG instance."""
    global _vcad_dag
    if _vcad_dag is None:
        _vcad_dag = VcadDag()
    return _vcad_dag


def _reset_vcad_dag() -> None:
    """Reset the global DAG instance (for testing)."""
    global _vcad_dag
    _vcad_dag = None


# ---------------------------------------------------------------------------
# Error handling helpers
# ---------------------------------------------------------------------------


def _handle_vcad_error(e: Exception, operation: str) -> str:
    """Standardized error handling for VCAD sidecar errors.

    Preserves upstream error_code and details unchanged.
    Driver must not rewrite upstream error_code; it may only enrich
    missing details.operation.
    """
    if isinstance(e, VCADCapabilityError):
        logger.error(f"Capability error during {operation}: {e}")
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "error_code": e.error_code,
                "details": e.details,
            }
        )
    if isinstance(e, VCADProtocolError):
        logger.error(f"Protocol error during {operation}: {e}")
        response: dict[str, Any] = {
            "success": False,
            "error": str(e),
            "error_code": e.error_code,
        }
        if e.details:
            response["details"] = e.details
        return json.dumps(response)
    if isinstance(e, VCADRemoteError):
        logger.error(f"Remote error during {operation}: {e}")
        response = {
            "success": False,
            "error": e.message,
            "error_code": e.code,
        }
        if e.data:
            response["details"] = e.data
        return json.dumps(response)
    if isinstance(e, (VCADConnectionError, VCADTimeoutError)):
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
# DAG helpers
# ---------------------------------------------------------------------------


def _build_import_refs(
    import_decls: list[dict[str, Any]],
    resolved_imports: dict[str, Any],
) -> list[ImportRef]:
    """Build ImportRef list from extraction and resolution results."""
    refs = []
    for imp in import_decls:
        import_id = imp.get("import_id", "")
        resolved = resolved_imports.get(import_id, {})

        # Determine resolved type: solid imports from vcad-backed entities
        # carry vcad_node_id; data imports may have resolved_type set directly.
        extract = imp.get("extract", "")
        vcad_node_id = resolved.get("vcad_node_id")
        if extract == "solid" and vcad_node_id:
            resolved_type = "vcad"
            source_node_id = vcad_node_id
        else:
            resolved_type = resolved.get("resolved_type", "native")
            source_node_id = resolved.get("source_node_id")

        refs.append(ImportRef(
            binding_name=imp.get("injected_symbol", imp.get("binding_name", "")),
            entity_ref=imp.get("entity_ref", ""),
            extract=extract,
            resolved_type=resolved_type,
            source_node_id=source_node_id,
        ))
    return refs


def _vcad_update_single(
    ctx: McpContext,
    node_id: str,
    source_file: str,
    revision: int,
    dag: VcadDag,
) -> dict[str, Any]:
    """Internal helper: re-evaluate a single node with revision guard.

    Returns result dict with success/error status.
    """
    agent = get_agent_name(ctx)

    # Re-evaluate via sidecar
    try:
        vcad = get_vcad_connection(agent=agent)
        eval_result = vcad.eval_file(source_file)
    except Exception as e:
        return {"success": False, "node_id": node_id, "error": str(e)}

    obj_path = eval_result.get("obj_path")
    if not obj_path:
        return {
            "success": False,
            "node_id": node_id,
            "error": "Sidecar did not return obj_path",
        }

    # Check revision freshness before applying
    if not dag.should_apply(node_id, revision):
        return {
            "success": False,
            "node_id": node_id,
            "error": "Stale revision dropped",
            "error_type": "stale",
            "revision": revision,
        }

    # Apply in SketchUp
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
    except Exception as e:
        return {"success": False, "node_id": node_id, "error": str(e)}

    # Mark applied and persist
    dag.mark_applied(node_id, revision)
    node = dag.get_node(node_id)
    if node:
        node.last_entity_id = result.get("entity_id", node.last_entity_id)
    dag.persist_state()

    return {"success": True, "node_id": node_id, "revision": revision}


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

    1. Send source file to VCAD sidecar for evaluation -> OBJ file
    2. Send OBJ path to SketchUp -> definitions.import -> ComponentDefinition
    3. Store VCAD metadata in attribute dictionary

    Args:
        ctx: MCP context
        node_id: Unique identifier for this VCAD node
        source_file: Path to the .skp.oo file
        position: Optional [x, y, z] position in mm (default [0, 0, 0])
        component_name: Optional name for the SketchUp component
    """
    agent = get_agent_name(ctx)

    # Step 1: Evaluate source file via VCAD sidecar
    try:
        vcad = get_vcad_connection(agent=agent)
        eval_result = vcad.eval_file(source_file)
    except (
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
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

        # Register node in DAG (no imports for simple place)
        dag = get_vcad_dag()
        dag_node = VcadNode(
            node_id=node_id,
            source_file=source_file,
            last_entity_id=result.get("entity_id"),
        )
        dag.add_node(dag_node)
        dag.persist_state()

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
    """Re-evaluate VCAD node and update SketchUp geometry.

    If source_file is not provided, queries SketchUp for the node's
    current source_file attribute.

    Args:
        ctx: MCP context
        node_id: The VCAD node identifier to update
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
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
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

        # Refresh DAG entry (imports may have changed)
        dag = get_vcad_dag()
        existing = dag.get_node(node_id)
        if existing:
            existing.source_file = source_file
            existing.last_entity_id = result.get("entity_id", existing.last_entity_id)
            dag.add_node(existing)
        else:
            dag.add_node(VcadNode(
                node_id=node_id,
                source_file=source_file,
                last_entity_id=result.get("entity_id"),
            ))
        dag.persist_state()

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
    """Inspect VCAD geometry: volume, surface area, bounding box.

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
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
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
    """Export VCAD geometry to OBJ or STEP.

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
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_export")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_export")


@mcp.tool()
def vcad_eval(ctx: McpContext, code: str) -> str:
    """Evaluate Loon code in VCAD sidecar (REPL mode). Returns display string.

    Args:
        ctx: MCP context
        code: Loon source code to evaluate
    """
    try:
        vcad = get_vcad_connection(agent=get_agent_name(ctx))
        result = vcad.eval_code(code)
        return json.dumps({"success": True, **result})
    except (
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_eval")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_eval")


@mcp.tool()
def vcad_place_with_imports(
    ctx: McpContext,
    node_id: str,
    source_file: str,
    position: list[float] | None = None,
    component_name: str | None = None,
) -> str:
    """Place vcad node with data references from SketchUp entities.

    Imports are declared inline in source using:
      [let <binding> [import :dimensions|:bbox|:transform "entity:<id>"]]
    and are resolved by sidecar+driver before evaluation.

    Args:
        ctx: MCP context
        node_id: Unique identifier for this VCAD node
        source_file: Path to the .skp.oo file
        position: Optional [x, y, z] position in mm (default [0, 0, 0])
        component_name: Optional name for the SketchUp component
    """
    agent = get_agent_name(ctx)

    # Step 1: Read source file
    try:
        with open(source_file) as f:
            source = f.read()
    except OSError as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Cannot read source file: {e}",
                "error_type": "io",
            }
        )

    # Step 2: Extract imports via sidecar (parse-only, fast-path)
    try:
        vcad = get_vcad_connection(agent=agent)
        extraction = vcad.extract_imports(source)
    except (
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_place_with_imports:extract")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_place_with_imports:extract")

    import_decls = extraction.get("imports", [])
    transformed_source = extraction.get("transformed_source", source)

    # Step 3: Resolve each import via SketchUp bridge
    resolved_imports: dict[str, Any] = {}
    has_solid_imports = False
    if import_decls:
        try:
            sketchup = get_sketchup_connection(agent=agent)
            for imp in import_decls:
                entity_ref = imp["entity_ref"]
                entity_id_str = entity_ref.split(":", 1)[1] if ":" in entity_ref else ""

                resolve_result = sketchup.send_command(
                    method="resolve_vcad_import",
                    params={
                        "entity_id": entity_id_str,
                        "extract": imp["extract"],
                    },
                    request_id=ctx.request_id,
                )

                if imp["extract"] == "solid":
                    # Solid import: ADT retrieved from sidecar cache by vcad_node_id
                    has_solid_imports = True
                    resolved_imports[imp["import_id"]] = {
                        "extract": "solid",
                        "injected_symbol": imp["injected_symbol"],
                        "data": None,
                        "vcad_node_id": resolve_result.get("vcad_node_id"),
                    }
                else:
                    # Data import: resolved data injected as Loon let-binding
                    resolved_imports[imp["import_id"]] = {
                        "extract": imp["extract"],
                        "injected_symbol": imp["injected_symbol"],
                        "data": resolve_result.get("data", {}),
                    }
        except (
            SketchUpRemoteError,
            SketchUpConnectionError,
            SketchUpTimeoutError,
            SketchUpProtocolError,
        ) as e:
            return _handle_sketchup_error(e, "vcad_place_with_imports:resolve")
        except Exception as e:
            return _handle_sketchup_error(e, "vcad_place_with_imports:resolve")

    # Step 4: Evaluate with resolved imports via sidecar
    try:
        vcad = get_vcad_connection(agent=agent)
        base_dir = os.path.dirname(os.path.abspath(source_file))
        if has_solid_imports:
            # Use solid-aware eval path (ADT composition)
            eval_result = vcad.eval_with_solid_imports(
                transformed_source=transformed_source,
                base_dir=base_dir,
                imports=resolved_imports,
                node_id=node_id,
            )
        else:
            eval_result = vcad.eval_with_imports(
                transformed_source=transformed_source,
                base_dir=base_dir,
                imports=resolved_imports,
            )
    except (
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_place_with_imports:eval")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_place_with_imports:eval")

    obj_path = eval_result.get("obj_path")
    if not obj_path:
        return json.dumps(
            {
                "success": False,
                "error": "Sidecar did not return obj_path",
                "error_type": "unexpected",
            }
        )

    # Step 5: Place in SketchUp via Ruby bridge
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

        # Register node with imports in DAG
        dag = get_vcad_dag()
        dag_imports = _build_import_refs(import_decls, resolved_imports)
        dag_node = VcadNode(
            node_id=node_id,
            source_file=source_file,
            imports=dag_imports,
            last_entity_id=result.get("entity_id"),
        )
        dag.add_node(dag_node)
        dag.persist_state()

        return json.dumps(result)
    except (
        SketchUpRemoteError,
        SketchUpConnectionError,
        SketchUpTimeoutError,
        SketchUpProtocolError,
    ) as e:
        return _handle_sketchup_error(e, "vcad_place_with_imports:import")
    except Exception as e:
        return _handle_sketchup_error(e, "vcad_place_with_imports:import")


@mcp.tool()
def vcad_list_nodes(ctx: McpContext) -> str:
    """List all VCAD nodes in the current SketchUp model."""
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


@mcp.tool()
def vcad_update_cascade(ctx: McpContext, node_id: str) -> str:
    """Re-evaluate node and all downstream dependents in topological order.

    ADT composition: each node's ADT tree is cached in the sidecar,
    so downstream nodes that import :solid get the fresh ADT directly.

    This is a manually triggered tool -- the agent (or user) calls it
    explicitly after editing a source file.

    Args:
        ctx: MCP context
        node_id: The root VCAD node to re-evaluate
    """
    dag = get_vcad_dag()

    root_node = dag.get_node(node_id)
    if not root_node:
        return json.dumps({
            "success": False,
            "error": f"Node {node_id} not found in DAG",
            "error_type": "not_found",
        })

    # Build affected set: root + all downstream
    downstream = dag.get_downstream(node_id)
    affected = [node_id] + downstream
    order = dag._topological_sort(affected)

    results = []
    for nid in order:
        node = dag.get_node(nid)
        if not node:
            results.append({
                "success": False,
                "node_id": nid,
                "error": "Node not found in DAG",
            })
            continue

        if node.status == "degraded":
            results.append({
                "success": False,
                "node_id": nid,
                "error": "Node is degraded",
                "error_code": "SOURCE_FILE_MISSING",
            })
            continue

        revision = dag.bump_revision(nid)
        result = _vcad_update_single(ctx, nid, node.source_file, revision, dag)
        results.append(result)

    return json.dumps({
        "success": all(r.get("success") for r in results),
        "updated": [r["node_id"] for r in results if r.get("success")],
        "failed": [r["node_id"] for r in results if not r.get("success")],
        "results": results,
    })
