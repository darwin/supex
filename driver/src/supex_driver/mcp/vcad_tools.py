"""MCP tools for VCAD BRep evaluation and SketchUp placement."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from supex_driver.connection import (
    get_sketchup_connection,
    get_vcad_connection,
)
from supex_driver.connection.sketchup_exceptions import (
    SketchUpConnectionError,
    SketchUpProtocolError,
    SketchUpRemoteError,
    SketchUpTimeoutError,
)
from supex_driver.connection.vcad_dag import ImportRef, VCADDag, VCADNode
from supex_driver.connection.vcad_exceptions import (
    VCADCapabilityError,
    VCADConnectionError,
    VCADProtocolError,
    VCADRemoteError,
    VCADTimeoutError,
)
from supex_driver.connection.vcad_file_watcher import (
    get_vcad_file_watcher,
)
from supex_driver.connection.vcad_observer import (
    get_vcad_reactive_watcher,
)
from supex_driver.connection.vcad_schema import build_error
from supex_driver.mcp.mcp_server import McpContext, get_agent_name, mcp

logger = logging.getLogger("supex.mcp.vcad")

# ---------------------------------------------------------------------------
# Workspace boundary validation
# ---------------------------------------------------------------------------


def validate_workspace_path(path: str, workspace: Path) -> Path:
    """Validate and canonicalize a source file path within workspace boundary.

    Resolves relative paths against the workspace root. Rejects paths that
    escape the workspace via traversal (``../``) or symlink.

    Args:
        path: The source file path to validate (absolute or relative).
        workspace: The workspace root directory.

    Returns:
        Resolved canonical Path guaranteed to be within the workspace.

    Raises:
        ValueError: If the resolved path is outside the workspace.
    """
    workspace_canonical = workspace.resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = workspace_canonical / candidate
    resolved = candidate.resolve()

    ws_str = str(workspace_canonical)
    if resolved != workspace_canonical and not str(resolved).startswith(ws_str + os.sep):
        raise ValueError(f"Path escapes workspace boundary: {path}")

    return resolved


def _check_source_boundary(
    source_file: str, operation: str,
) -> tuple[str, dict[str, Any] | None]:
    """Validate source file path against workspace boundary.

    Fail-closed: if ``SUPEX_WORKSPACE`` is not set, all reads are denied.

    Returns:
        ``(resolved_path, None)`` on success, or
        ``(original_path, error_dict)`` on denial.
    """
    workspace_env = os.environ.get("SUPEX_WORKSPACE")
    if not workspace_env:
        return source_file, build_error(
            "PATH_NOT_ALLOWED",
            "SUPEX_WORKSPACE not set: cannot validate source file path",
            {"path": source_file, "workspace": "(unset)"},
            operation=operation,
        )
    try:
        resolved = validate_workspace_path(source_file, Path(workspace_env))
        return str(resolved), None
    except ValueError:
        return source_file, build_error(
            "PATH_NOT_ALLOWED",
            f"Source file path outside workspace boundary: {source_file}",
            {"path": source_file, "workspace": workspace_env},
            operation=operation,
        )


# ---------------------------------------------------------------------------
# DAG singleton
# ---------------------------------------------------------------------------

_vcad_dag: VCADDag | None = None


def get_vcad_dag() -> VCADDag:
    """Get or create the global VCAD DAG instance."""
    global _vcad_dag
    if _vcad_dag is None:
        _vcad_dag = VCADDag()
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

    Uses build_error() to produce validated error envelopes at the MCP
    boundary.  Preserves upstream error_code and details unchanged;
    driver may only enrich missing details.operation.
    """
    if isinstance(e, VCADCapabilityError):
        logger.error(f"Capability error during {operation}: {e}")
        return json.dumps(build_error(e.error_code, str(e), e.details, operation))
    if isinstance(e, VCADProtocolError):
        logger.error(f"Protocol error during {operation}: {e}")
        return json.dumps(
            build_error(e.error_code or "PROTOCOL_ERROR", str(e), e.details, operation)
        )
    if isinstance(e, VCADRemoteError):
        logger.error(f"Remote error during {operation}: {e}")
        return json.dumps(build_error(e.code, e.message, e.data or None, operation))
    if isinstance(e, (VCADConnectionError, VCADTimeoutError)):
        logger.error(f"Connection error during {operation}: {e}")
        return json.dumps(
            build_error("CONNECTION_ERROR", str(e), {"error_type": "connection"}, operation)
        )
    logger.exception(f"Unexpected error during {operation}: {e}")
    return json.dumps(
        build_error("INTERNAL_ERROR", str(e), {"error_type": "unexpected"}, operation)
    )


def _handle_sketchup_error(e: Exception, operation: str) -> str:
    """Standardized error handling for SketchUp bridge errors.

    Uses build_error() to produce validated error envelopes at the MCP
    boundary.
    """
    if isinstance(e, SketchUpRemoteError):
        logger.error(f"Remote error during {operation}: {e}")
        return json.dumps(
            build_error(e.code, e.message, {"error_type": "remote"}, operation)
        )
    if isinstance(e, (SketchUpConnectionError, SketchUpTimeoutError)):
        logger.error(f"Connection error during {operation}: {e}")
        return json.dumps(
            build_error("CONNECTION_ERROR", str(e), {"error_type": "connection"}, operation)
        )
    if isinstance(e, SketchUpProtocolError):
        logger.error(f"Protocol error during {operation}: {e}")
        return json.dumps(
            build_error("PROTOCOL_ERROR", str(e), {"error_type": "protocol"}, operation)
        )
    logger.exception(f"Unexpected error during {operation}: {e}")
    return json.dumps(
        build_error("INTERNAL_ERROR", str(e), {"error_type": "unexpected"}, operation)
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
        extracts = imp.get("extracts", [])
        vcad_node_id = resolved.get("vcad_node_id")
        if "solid" in extracts and vcad_node_id:
            resolved_type = "vcad"
            source_node_id = vcad_node_id
        else:
            resolved_type = resolved.get("resolved_type", "native")
            source_node_id = resolved.get("source_node_id")

        refs.append(ImportRef(
            binding_name=imp.get("injected_symbol", imp.get("binding_name", "")),
            selector=imp.get("selector", ""),
            source=imp.get("source", "host"),
            extracts=extracts,
            resolved_type=resolved_type,
            source_node_id=source_node_id,
        ))
    return refs


def _resolve_imports(
    ctx: McpContext,
    source_text: str,
    source_file: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Extract and resolve imports from source text.

    Returns (has_imports, details) where details contains:
    - transformed_source, import_decls, resolved_imports, has_solid_imports
    """
    # Quick syntactic check: skip sidecar call when no import keyword present
    if "[import " not in source_text:
        return (False, {})

    agent = get_agent_name(ctx)

    # Step 1: Extract imports via sidecar (parse-only, fast-path)
    vcad = get_vcad_connection(agent=agent)
    extraction = vcad.extract_imports(source_text)

    import_decls = extraction.get("imports", [])
    transformed_source = extraction.get("transformed_source", source_text)

    if not import_decls:
        return (False, {})

    # Step 2: Resolve each import via SketchUp bridge
    resolved_imports: dict[str, Any] = {}
    has_solid_imports = False
    sketchup = get_sketchup_connection(agent=agent)

    for imp in import_decls:
        selector = imp["selector"]
        # Extract entity ID from selector (for :host source)
        entity_id_str = selector.split(":", 1)[1] if ":" in selector else ""
        extracts = imp.get("extracts", [])

        if "solid" in extracts:
            # Solid import — single extract
            resolve_result = sketchup.send_command(
                method="resolve_vcad_import",
                params={
                    "entity_id": entity_id_str,
                    "extract": "solid",
                },
                request_id=ctx.request_id,
            )
            has_solid_imports = True
            resolve_source = resolve_result.get("source", "vcad")
            if resolve_source == "native_mesh":
                resolved_imports[imp["import_id"]] = {
                    "extract": "solid",
                    "injected_symbol": imp["injected_symbol"],
                    "source": "native_mesh",
                    "data": None,
                    "vcad_node_id": None,
                    "native_mesh": resolve_result.get("mesh"),
                    "resolved_type": "native_mesh",
                }
            else:
                resolved_imports[imp["import_id"]] = {
                    "extract": "solid",
                    "injected_symbol": imp["injected_symbol"],
                    "data": None,
                    "vcad_node_id": resolve_result.get("vcad_node_id"),
                }
        elif len(extracts) == 1:
            # Single data extract — request directly
            resolve_result = sketchup.send_command(
                method="resolve_vcad_import",
                params={
                    "entity_id": entity_id_str,
                    "extract": extracts[0],
                },
                request_id=ctx.request_id,
            )
            resolved_imports[imp["import_id"]] = {
                "extract": extracts[0],
                "injected_symbol": imp["injected_symbol"],
                "data": resolve_result.get("data", {}),
            }
        else:
            # No extracts (all) or multiple extracts — request all, then filter
            resolve_result = sketchup.send_command(
                method="resolve_vcad_import",
                params={
                    "entity_id": entity_id_str,
                    "extract": "all",
                },
                request_id=ctx.request_id,
            )
            all_data = resolve_result.get("data", {})
            if extracts:
                # Multi-extract: filter to requested keys
                filtered_data = {k: all_data[k] for k in extracts if k in all_data}
                resolved_imports[imp["import_id"]] = {
                    "extract": "all",
                    "injected_symbol": imp["injected_symbol"],
                    "data": filtered_data,
                }
            else:
                resolved_imports[imp["import_id"]] = {
                    "extract": "all",
                    "injected_symbol": imp["injected_symbol"],
                    "data": all_data,
                }

    return (True, {
        "transformed_source": transformed_source,
        "import_decls": import_decls,
        "resolved_imports": resolved_imports,
        "has_solid_imports": has_solid_imports,
    })


def _eval_with_imports(
    ctx: McpContext,
    details: dict[str, Any],
    base_dir: str | None = None,
    node_id: str | None = None,
    display: bool = False,
    cache_adt: bool = False,
    track_modules: bool = False,
    inspect: bool = False,
    export_mesh: bool = True,
) -> dict[str, Any]:
    """Evaluate transformed source with resolved imports via sidecar."""
    agent = get_agent_name(ctx)
    vcad = get_vcad_connection(agent=agent)

    return vcad.eval_with_imports(
        transformed_source=details["transformed_source"],
        base_dir=base_dir,
        imports=details.get("resolved_imports", {}),
        node_id=node_id,
        display=display,
        cache_adt=cache_adt,
        track_modules=track_modules,
        inspect=inspect,
        export_mesh=export_mesh,
    )


def _vcad_update_single(  # noqa: PLR0911
    ctx: McpContext,
    node_id: str,
    source_file: str,
    revision: int,
    dag: VCADDag,
) -> dict[str, Any]:
    """Internal helper: re-evaluate a single node with revision guard.

    Auto-detects imports in source and resolves them before evaluation.
    Returns result dict with success/error status.
    """
    agent = get_agent_name(ctx)

    # Workspace boundary check
    source_file, boundary_err = _check_source_boundary(source_file, "vcad_update:cascade:read")
    if boundary_err:
        return boundary_err

    # Read source and check for imports
    try:
        with open(source_file) as f:
            source_text = f.read()
    except OSError as e:
        return build_error("IO_ERROR", f"Cannot read source file: {e}", {"node_id": node_id})

    try:
        has_imports, details = _resolve_imports(ctx, source_text, source_file)
    except Exception as e:
        return build_error("INTERNAL_ERROR", str(e), {"node_id": node_id})

    # Re-evaluate via sidecar
    try:
        if not has_imports:
            details = {"transformed_source": source_text, "resolved_imports": {}}
        base_dir = os.path.dirname(os.path.abspath(source_file))
        eval_result = _eval_with_imports(
            ctx, details, base_dir=base_dir, node_id=node_id,
            cache_adt=True, track_modules=True, export_mesh=True,
        )
    except Exception as e:
        return build_error("INTERNAL_ERROR", str(e), {"node_id": node_id})

    mesh_path = eval_result.get("mesh_path")
    if not mesh_path:
        return build_error(
            "UNEXPECTED_ERROR", "Sidecar did not return mesh_path", {"node_id": node_id}
        )

    # Check revision freshness before applying
    if not dag.should_apply(node_id, revision):
        return build_error(
            "STALE_REVISION", "Stale revision dropped",
            {"node_id": node_id, "revision": revision},
        )

    # Apply in SketchUp
    try:
        sketchup = get_sketchup_connection(agent=agent)
        result = sketchup.send_command(
            method="update_vcad_node",
            params={
                "mesh_path": mesh_path,
                "node_id": node_id,
                "source_file": source_file,
            },
            request_id=ctx.request_id,
        )
    except Exception as e:
        return build_error("INTERNAL_ERROR", str(e), {"node_id": node_id})

    # Update DAG with import refs if applicable
    if has_imports:
        node = dag.get_node(node_id)
        if node:
            node.imports = _build_import_refs(
                details["import_decls"], details["resolved_imports"]
            )

    # Mark applied and persist
    dag.mark_applied(node_id, revision)
    node = dag.get_node(node_id)
    if node:
        node.last_entity_id = result.get("entity_id", node.last_entity_id)
    dag.persist_state()

    # Push to viewer relay (best-effort, never breaks main flow)
    try:
        from supex_driver.connection.vcad_viewer_relay import _relay

        if _relay is not None:
            _relay.push_file_update(
                node_id, revision, mesh_path, eval_result.get("bbox"),
            )
    except Exception:
        pass

    return {"success": True, "node_id": node_id, "revision": revision}


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
def vcad_place(  # noqa: PLR0911
    ctx: McpContext,
    node_id: str,
    source_file: str,
    position: list[float] | None = None,
    component_name: str | None = None,
) -> str:
    """Evaluate a .cmp.oo file and place the resulting mesh in SketchUp.

    1. Send source file to VCAD sidecar for evaluation -> DAE mesh file
    2. Send mesh path to SketchUp -> definitions.import -> ComponentDefinition
    3. Store VCAD metadata in attribute dictionary

    Args:
        ctx: MCP context
        node_id: Unique identifier for this VCAD node
        source_file: Path to the .cmp.oo file
        position: Optional [x, y, z] position in mm (default [0, 0, 0])
        component_name: Optional name for the SketchUp component
    """
    agent = get_agent_name(ctx)

    # Workspace boundary check
    source_file, boundary_err = _check_source_boundary(source_file, "vcad_place:read")
    if boundary_err:
        return json.dumps(boundary_err)

    # Step 1: Read source and check for imports
    try:
        with open(source_file) as f:
            source_text = f.read()
    except OSError as e:
        return json.dumps(
            build_error("IO_ERROR", f"Cannot read source file: {e}", operation="vcad_place:read")
        )

    try:
        has_imports, details = _resolve_imports(ctx, source_text, source_file)
    except (
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_place:extract")
    except (
        SketchUpRemoteError,
        SketchUpConnectionError,
        SketchUpTimeoutError,
        SketchUpProtocolError,
    ) as e:
        return _handle_sketchup_error(e, "vcad_place:resolve")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_place:extract")

    # Step 2: Evaluate via sidecar
    try:
        if not has_imports:
            details = {"transformed_source": source_text, "resolved_imports": {}}
        base_dir = os.path.dirname(os.path.abspath(source_file))
        eval_result = _eval_with_imports(
            ctx, details, base_dir=base_dir, node_id=node_id,
            cache_adt=True, track_modules=True, export_mesh=True,
        )
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

    mesh_path = eval_result.get("mesh_path")
    if not mesh_path:
        return json.dumps(
            build_error("UNEXPECTED_ERROR", "Sidecar did not return mesh_path", operation="vcad_place:eval")
        )

    # Step 3: Place in SketchUp via Ruby bridge
    try:
        sketchup = get_sketchup_connection(agent=agent)
        place_params: dict[str, Any] = {
            "mesh_path": mesh_path,
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

        # Register node in DAG (with imports if applicable)
        dag = get_vcad_dag()
        dag_imports = (
            _build_import_refs(details["import_decls"], details["resolved_imports"])
            if has_imports else []
        )
        dag_node = VCADNode(
            node_id=node_id,
            source_file=source_file,
            imports=dag_imports,
            last_entity_id=result.get("entity_id"),
        )
        dag.add_node(dag_node)
        dag.persist_state()

        # Auto-start file watcher on first place
        watcher = get_vcad_file_watcher()
        vcad_conn = get_vcad_connection(agent=agent)
        watcher.auto_start_if_needed(source_file, vcad_conn)

        # Push to viewer relay (best-effort, never breaks main flow)
        try:
            from supex_driver.connection.vcad_viewer_relay import _relay

            if _relay is not None:
                _relay.push_file_update(
                    node_id, 1, mesh_path, eval_result.get("bbox"),
                )
        except Exception:
            pass

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
def vcad_update(ctx: McpContext, node_id: str, source_file: str | None = None, cascade: bool = False) -> str:  # noqa: PLR0911
    """Re-evaluate VCAD node and update SketchUp geometry.

    If source_file is not provided, queries SketchUp for the node's
    current source_file attribute.

    Args:
        ctx: MCP context
        node_id: The VCAD node identifier to update
        source_file: Optional new source file path (uses existing if omitted)
        cascade: When True, also re-evaluate all downstream dependents in topological order
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
                    build_error(
                        "UNEXPECTED_ERROR",
                        f"No source_file found for node {node_id}",
                        {"node_id": node_id},
                        operation="vcad_update:lookup",
                    )
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

    # Workspace boundary check
    source_file, boundary_err = _check_source_boundary(source_file, "vcad_update:read")
    if boundary_err:
        return json.dumps(boundary_err)

    # Read source and check for imports
    try:
        with open(source_file) as f:
            source_text = f.read()
    except OSError as e:
        return json.dumps(
            build_error("IO_ERROR", f"Cannot read source file: {e}", operation="vcad_update:read")
        )

    try:
        has_imports, details = _resolve_imports(ctx, source_text, source_file)
    except (
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_update:extract")
    except (
        SketchUpRemoteError,
        SketchUpConnectionError,
        SketchUpTimeoutError,
        SketchUpProtocolError,
    ) as e:
        return _handle_sketchup_error(e, "vcad_update:resolve")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_update:extract")

    # Re-evaluate via sidecar
    try:
        if not has_imports:
            details = {"transformed_source": source_text, "resolved_imports": {}}
        base_dir = os.path.dirname(os.path.abspath(source_file))
        eval_result = _eval_with_imports(
            ctx, details, base_dir=base_dir, node_id=node_id,
            cache_adt=True, track_modules=True, export_mesh=True,
        )
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

    mesh_path = eval_result.get("mesh_path")
    if not mesh_path:
        return json.dumps(
            build_error("UNEXPECTED_ERROR", "Sidecar did not return mesh_path", operation="vcad_update:eval")
        )

    # Update in SketchUp via Ruby bridge
    try:
        sketchup = get_sketchup_connection(agent=agent)
        result = sketchup.send_command(
            method="update_vcad_node",
            params={
                "mesh_path": mesh_path,
                "node_id": node_id,
                "source_file": source_file,
            },
            request_id=ctx.request_id,
        )

        # Refresh DAG entry (imports may have changed)
        dag = get_vcad_dag()
        dag_imports = (
            _build_import_refs(details["import_decls"], details["resolved_imports"])
            if has_imports else []
        )
        existing = dag.get_node(node_id)
        if existing:
            existing.source_file = source_file
            existing.imports = dag_imports
            existing.last_entity_id = result.get("entity_id", existing.last_entity_id)
            dag.add_node(existing)
        else:
            dag.add_node(VCADNode(
                node_id=node_id,
                source_file=source_file,
                imports=dag_imports,
                last_entity_id=result.get("entity_id"),
            ))
        dag.persist_state()

        # Push to viewer relay (best-effort, never breaks main flow)
        try:
            from supex_driver.connection.vcad_viewer_relay import _relay

            if _relay is not None:
                dag_node = dag.get_node(node_id)
                rev = dag_node.applied_revision if dag_node else 1
                _relay.push_file_update(
                    node_id, rev, mesh_path, eval_result.get("bbox"),
                )
        except Exception:
            pass

        if not cascade:
            return json.dumps(result)

        # Cascade: re-evaluate downstream dependents in topological order
        downstream = dag.get_downstream(node_id)
        if not downstream:
            return json.dumps(result)

        affected = [node_id] + downstream
        order = dag._topological_sort(affected)

        cascade_results = [result]
        for nid in order:
            if nid == node_id:
                continue  # root already updated above
            node = dag.get_node(nid)
            if not node:
                cascade_results.append(
                    build_error("NODE_NOT_FOUND", "Node not found in DAG", {"node_id": nid})
                )
                continue
            if node.status == "degraded":
                cascade_results.append(
                    build_error("SOURCE_FILE_MISSING", "Node is degraded", {
                        "node_id": nid,
                        "source_file": node.source_file,
                    }, operation="vcad_update")
                )
                continue
            revision = dag.bump_revision(nid)
            cascade_results.append(_vcad_update_single(ctx, nid, node.source_file, revision, dag))

        return json.dumps({
            "success": all(r.get("success") for r in cascade_results),
            "updated": [r["node_id"] for r in cascade_results if r.get("success")],
            "failed": [r["node_id"] for r in cascade_results if not r.get("success")],
            "results": cascade_results,
        })
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

    Source can be a .cmp.oo file path or inline Loon code.

    Args:
        ctx: MCP context
        source: A .cmp.oo file path or inline Loon code
    """
    try:
        # Read source text if it's a file path
        is_file = source.endswith(".oo") or source.endswith(".loon")
        if is_file:
            source, boundary_err = _check_source_boundary(source, "vcad_inspect:read")
            if boundary_err:
                return json.dumps(boundary_err)
            try:
                with open(source) as f:
                    source_text = f.read()
            except OSError as e:
                return json.dumps(
                    build_error("IO_ERROR", f"Cannot read source file: {e}", operation="vcad_inspect:read")
                )
        else:
            source_text = source

        has_imports, details = _resolve_imports(ctx, source_text, source if is_file else None)

        if not has_imports:
            details = {"transformed_source": source_text, "resolved_imports": {}}
        base_dir = os.path.dirname(os.path.abspath(source)) if is_file else None
        eval_result = _eval_with_imports(ctx, details, base_dir=base_dir, inspect=True, export_mesh=False)
        return json.dumps({
            "success": True,
            "volume": eval_result.get("volume", 0.0),
            "surface_area": eval_result.get("surface_area", 0.0),
            "bbox": eval_result.get("bbox", {}),
            "is_empty": eval_result.get("is_empty", False),
        })
    except (
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_inspect")
    except (
        SketchUpRemoteError,
        SketchUpConnectionError,
        SketchUpTimeoutError,
        SketchUpProtocolError,
    ) as e:
        return _handle_sketchup_error(e, "vcad_inspect")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_inspect")


@mcp.tool()
def vcad_eval(ctx: McpContext, code: str) -> str:
    """Evaluate Loon code in VCAD sidecar (REPL mode). Returns display string.

    Args:
        ctx: MCP context
        code: Loon source code to evaluate
    """
    try:
        has_imports, details = _resolve_imports(ctx, code)

        if not has_imports:
            details = {"transformed_source": code, "resolved_imports": {}}
        result = _eval_with_imports(ctx, details, display=True, export_mesh=False)
        return json.dumps({"success": True, **result})
    except (
        VCADCapabilityError,
        VCADProtocolError,
        VCADRemoteError,
        VCADConnectionError,
        VCADTimeoutError,
    ) as e:
        return _handle_vcad_error(e, "vcad_eval")
    except (
        SketchUpRemoteError,
        SketchUpConnectionError,
        SketchUpTimeoutError,
        SketchUpProtocolError,
    ) as e:
        return _handle_sketchup_error(e, "vcad_eval")
    except Exception as e:
        return _handle_vcad_error(e, "vcad_eval")


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
def vcad_watch_pause(ctx: McpContext) -> str:
    """Pause reactive watching. Changes accumulate but don't trigger re-evaluation.

    Use this before editing multiple .cmp.oo files in sequence, then call
    vcad_watch_resume to flush all changes as a single cascade.
    """
    watcher = get_vcad_reactive_watcher()
    result = watcher.pause()
    return json.dumps(result)


@mcp.tool()
def vcad_watch_resume(ctx: McpContext) -> str:
    """Resume watching and flush: re-evaluate all nodes affected by accumulated changes.

    All changes collected while paused are merged, deduplicated, topologically
    sorted, and executed as a single cascade.
    """
    watcher = get_vcad_reactive_watcher()
    result = watcher.resume()
    return json.dumps(result)
