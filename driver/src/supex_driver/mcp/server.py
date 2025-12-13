import atexit
import contextlib
import json
import logging
import os
import sys
from typing import IO, Any, TextIO, cast

from mcp.server import fastmcp
from mcp.server.fastmcp import Context, FastMCP

# Type alias for MCP Context (generic with Any for session/lifespan/request types)
McpContext = Context[Any, Any, Any]

from supex_driver import __version__
from supex_driver.connection import get_sketchup_connection
from supex_driver.connection.exceptions import (
    SketchUpConnectionError,
    SketchUpProtocolError,
    SketchUpRemoteError,
    SketchUpTimeoutError,
)

# Logger instance (configured when server starts)
logger = logging.getLogger("supex.mcp")

# MCP client identification (captured from clientInfo during initialization)
_mcp_client_name: str | None = None


def get_agent_name(ctx: McpContext | None = None) -> str:
    """Get agent name from MCP client info or environment.

    Priority:
    1. MCP clientInfo.name (from session.client_params.clientInfo)
    2. SUPEX_AGENT environment variable
    3. Default to "mcp"
    """
    global _mcp_client_name

    # Try to get from Context
    if ctx is not None:
        try:
            # Access: ctx.request_context.session.client_params.clientInfo.name
            request_context = getattr(ctx, 'request_context', None)
            if request_context:
                session = getattr(request_context, 'session', None)
                if session:
                    client_params = getattr(session, 'client_params', None)
                    if client_params:
                        client_info = getattr(client_params, 'clientInfo', None)
                        if client_info:
                            raw_name = getattr(client_info, 'name', None)
                            if raw_name and isinstance(raw_name, str):
                                name: str = cast(str, raw_name)
                                logger.info(f"Got client name from MCP clientInfo: {name}")
                                _mcp_client_name = name
                                return name
        except Exception as e:
            logger.debug(f"Error accessing MCP clientInfo: {e}")

    # Use stored MCP client name if available
    if _mcp_client_name:
        return _mcp_client_name

    # Fallback to environment variable
    if agent := os.environ.get("SUPEX_AGENT"):
        return agent

    # Default
    return "mcp"

# Flag to track if logging has been configured
_logging_configured = False
# Track open log files for cleanup
_log_files: list[IO[str]] = []


def _cleanup_log_files() -> None:
    """Close all open log files on exit."""
    for f in _log_files:
        with contextlib.suppress(Exception):
            f.close()


atexit.register(_cleanup_log_files)


class TeeStream:
    """Stream that writes to both original stream and log file"""

    def __init__(self, original_stream: TextIO, log_file: TextIO) -> None:
        self.original_stream = original_stream
        self.log_file = log_file

    def write(self, data: str) -> int:
        self.original_stream.write(data)
        self.log_file.write(data)
        self.log_file.flush()
        return len(data)

    def flush(self) -> None:
        self.original_stream.flush()
        self.log_file.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.original_stream, name)


def setup_logging() -> None:
    """Configure logging for the MCP server.

    Sets up file logging and configures the logging format.
    Only runs once, even if called multiple times.
    """
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True

    # Setup file logging for stderr only (stdout is used by MCP protocol)
    log_dir = os.environ.get("SUPEX_LOG_DIR", os.path.expanduser("~/.supex/logs"))
    try:
        os.makedirs(log_dir, exist_ok=True)
        stderr_log_file = os.path.join(log_dir, "stderr.log")

        # Redirect stderr to log file while preserving original
        stderr_logger = open(stderr_log_file, 'a', encoding='utf-8')
        _log_files.append(stderr_logger)

        # Only tee stderr, never stdout (MCP protocol uses stdout)
        sys.stderr = TeeStream(sys.stderr, stderr_logger)
    except OSError:
        # If we can't create log directory, continue without file logging
        pass

    # Configure logging to stderr to avoid interfering with MCP stdio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr
    )

    logger.info(f"Supex MCP Server version {__version__} starting up")
    logger.info(f"FastMCP version: {fastmcp.__version__}")


# Create MCP server
mcp = FastMCP("Supex")


def call_tool(
    ctx: McpContext,
    method: str,
    params: dict[str, Any] | None = None,
    operation: str = "operation"
) -> str:
    """Execute a tool call with standardized error handling.

    Args:
        ctx: MCP request context
        method: Tool method name to call
        params: Optional parameters for the tool
        operation: Description for error logging

    Returns:
        JSON string with result or error information
    """
    try:
        sketchup = get_sketchup_connection(agent=get_agent_name(ctx))
        result = sketchup.send_command(
            method=method,
            params=params or {},
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except (SketchUpConnectionError, SketchUpTimeoutError) as e:
        logger.error(f"Connection error during {operation}: {e}")
        return json.dumps({"success": False, "error": str(e), "error_type": "connection"})
    except SketchUpProtocolError as e:
        logger.error(f"Protocol error during {operation}: {e}")
        return json.dumps({"success": False, "error": str(e), "error_type": "protocol"})
    except SketchUpRemoteError as e:
        logger.error(f"Remote error during {operation}: {e}")
        return json.dumps({
            "success": False,
            "error": e.message,
            "error_type": "remote",
            "error_code": e.code
        })
    except Exception as e:
        logger.exception(f"Unexpected error during {operation}: {e}")
        return json.dumps({"success": False, "error": str(e), "error_type": "unexpected"})


# Status and connection tools
@mcp.tool()
def check_sketchup_status(ctx: McpContext) -> str:
    """Check if SketchUp is connected and responding"""
    try:
        sketchup = get_sketchup_connection(agent=get_agent_name(ctx))
        result = sketchup.send_command(
            method="ping", params={}, request_id=ctx.request_id
        )
        return json.dumps(
            {
                "status": "connected",
                "version": result.get("version", "unknown"),
                "message": "SketchUp is connected and responding",
            }
        )
    except (SketchUpConnectionError, SketchUpTimeoutError) as e:
        return json.dumps(
            {
                "status": "disconnected",
                "error": str(e),
                "error_type": "connection",
                "message": "Make sure the SketchUp extension is running",
            }
        )
    except SketchUpProtocolError as e:
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "error_type": "protocol",
                "message": "Communication error with SketchUp",
            }
        )
    except SketchUpRemoteError as e:
        return json.dumps(
            {
                "status": "error",
                "error": e.message,
                "error_type": "remote",
                "error_code": e.code,
                "message": "SketchUp execution error",
            }
        )
    except Exception as e:
        logger.exception(f"Unexpected error checking status: {e}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "error_type": "unexpected",
                "message": "Unexpected error occurred",
            }
        )


# Export functionality
@mcp.tool()
def export_scene(ctx: McpContext, format: str = "skp") -> str:
    """Export the current SketchUp scene

    Args:
        format: Export format (skp, obj, dae, stl, png, jpg)
    """
    return call_tool(ctx, "export_scene", {"format": format}, "export_scene")


# Ruby code evaluation
@mcp.tool()
def eval_ruby(ctx: McpContext, code: str) -> str:
    """Evaluate arbitrary Ruby code in SketchUp context

    Args:
        code: Ruby code to execute
    """
    try:
        logger.info(f"Evaluating Ruby code ({len(code)} characters)")

        sketchup = get_sketchup_connection(agent=get_agent_name(ctx))

        result = sketchup.send_command(
            method="eval_ruby", params={"code": code}, request_id=ctx.request_id
        )

        # Format response consistently
        response = {
            "success": True,
            "result": result.get("content", [{"text": "Success"}])[0].get(
                "text", "Success"
            )
            if isinstance(result.get("content"), list)
            and len(result.get("content", [])) > 0
            else result.get("result", "Success"),
        }

        return json.dumps(response)
    except (SketchUpConnectionError, SketchUpTimeoutError) as e:
        logger.error(f"Connection error evaluating Ruby code: {e}")
        return json.dumps({"success": False, "error": str(e), "error_type": "connection"})
    except SketchUpProtocolError as e:
        logger.error(f"Protocol error evaluating Ruby code: {e}")
        return json.dumps({"success": False, "error": str(e), "error_type": "protocol"})
    except SketchUpRemoteError as e:
        logger.error(f"Remote error evaluating Ruby code: {e}")
        return json.dumps({"success": False, "error": e.message, "error_type": "remote", "error_code": e.code})
    except Exception as e:
        logger.exception(f"Unexpected error evaluating Ruby code: {e}")
        return json.dumps({"success": False, "error": str(e), "error_type": "unexpected"})


# Console capture functionality
@mcp.tool()
def console_capture_status(ctx: McpContext) -> str:
    """Get console capture status and log file information"""
    return call_tool(ctx, "console_capture_status", {}, "console_capture_status")


# File-based Ruby evaluation tools
@mcp.tool()
def eval_ruby_file(ctx: McpContext, file_path: str) -> str:
    """Evaluate Ruby code from a file in SketchUp context

    Args:
        file_path: Absolute path to Ruby file to execute
    """
    logger.info(f"Evaluating Ruby file: {file_path}")
    return call_tool(ctx, "eval_ruby_file", {"file_path": file_path}, "eval_ruby_file")


# Introspection tools
@mcp.tool()
def get_model_info(ctx: McpContext) -> str:
    """Get basic information about the current SketchUp model

    Returns model statistics including:
    - title: Model title
    - units: Current units (meters, feet, etc.)
    - num_faces: Number of faces in the model
    - num_edges: Number of edges
    - num_groups: Number of groups
    - num_components: Number of component instances
    - modified: Whether model has unsaved changes
    """
    return call_tool(ctx, "get_model_info", {}, "get_model_info")


@mcp.tool()
def list_entities(ctx: McpContext, entity_type: str = "all") -> str:
    """List entities in the model

    Args:
        entity_type: Type to filter - one of: faces, edges, groups, components, all

    Returns list of entities with type, name, and layer information
    """
    return call_tool(ctx, "list_entities", {"entity_type": entity_type}, "list_entities")


@mcp.tool()
def get_selection(ctx: McpContext) -> str:
    """Get currently selected entities in SketchUp

    Returns:
    - count: Number of selected entities
    - entities: List of selected entities with details (type, properties)
    """
    return call_tool(ctx, "get_selection", {}, "get_selection")


@mcp.tool()
def get_layers(ctx: McpContext) -> str:
    """Get list of layers (tags) in the model

    Returns list of layers with name, visible state, and entity count
    """
    return call_tool(ctx, "get_layers", {}, "get_layers")


@mcp.tool()
def get_materials(ctx: McpContext) -> str:
    """Get list of materials in the model

    Returns list of materials with name, color, and texture information
    """
    return call_tool(ctx, "get_materials", {}, "get_materials")


@mcp.tool()
def get_camera_info(ctx: McpContext) -> str:
    """Get current camera position and settings

    Returns camera eye position, target, up vector, and field of view
    """
    return call_tool(ctx, "get_camera_info", {}, "get_camera_info")


@mcp.tool()
def take_screenshot(
    ctx: McpContext,
    width: int = 1920,
    height: int = 1080,
    transparent: bool = False,
    output_path: str | None = None
) -> str:
    """Take a screenshot of the current SketchUp view and save to disk

    IMPORTANT: Returns file path only (not image data) to save context tokens!
    Use Read tool to view the screenshot if needed.

    Args:
        width: Image width in pixels (default 1920)
        height: Image height in pixels (default 1080)
        transparent: Whether to use transparent background (default False)
        output_path: Optional custom path for screenshot. If not provided,
                     saves to .tmp/screenshots/ with timestamp

    Returns:
        JSON with file_path where screenshot was saved (~200 tokens vs 21k!)
        Use Read tool on the file_path to view screenshot if necessary
    """
    params: dict[str, int | bool | str] = {
        "width": width,
        "height": height,
        "transparent": transparent
    }
    if output_path:
        params["output_path"] = output_path
    return call_tool(ctx, "take_screenshot", params, "take_screenshot")


@mcp.tool()
def take_batch_screenshots(
    ctx: McpContext,
    shots: list[dict[str, Any]],
    output_dir: str | None = None,
    base_name: str = "screenshot",
    width: int = 1920,
    height: int = 1080,
    transparent: bool = False,
    restore_camera: bool = True
) -> str:
    """Take multiple screenshots with different camera positions in a single batch.

    Designed for zero visual flicker - renders happen offscreen while preserving
    the user's current view. Camera is restored after batch completes.

    Args:
        shots: List of shot specifications. Each shot is a dict with:
            - camera: Camera specification dict with:
                - type: Camera type (default "standard_view"):
                    - "standard_view" with view: "top"|"front"|"right"|"left"|"back"|"bottom"|"iso"
                    - "custom" with eye: [x,y,z], target: [x,y,z], optional up/fov/perspective
                    - "zoom_entity" with entity_ids: [id1, id2, ...], optional padding
                - zoom_extents: Boolean flag (default true). When true, automatically adjusts
                    camera distance to fit all visible content after setting direction.
                    For "custom" type: Set to false if you need exact eye/target positions!
                    When true, your specified positions will be overridden to fit content.
            - name: Optional custom name for the shot (used in filename)
            - width: Optional width override for this shot
            - height: Optional height override for this shot
            - isolate: Optional entity_id of Group/ComponentInstance to isolate.
                       When specified, opens the entity for editing and enables
                       "Hide rest of Model" so only that subtree is visible.
                       zoom_extents then works only on the isolated content.
        output_dir: Directory for screenshots. Defaults to .tmp/batch_screenshots/timestamp/
        base_name: Base filename for screenshots (default "screenshot")
        width: Default width for all shots (default 1920)
        height: Default height for all shots (default 1080)
        transparent: Use transparent background (default False)
        restore_camera: Restore original camera after batch (default True)

    Returns:
        JSON with success status, output directory, and array of results for each shot.
        Each result contains file_path (on success) or error message (on failure).

    Example:
        take_batch_screenshots(
            shots=[
                {"camera": {"type": "standard_view", "view": "front"}, "name": "front"},
                {"camera": {"type": "standard_view", "view": "top"}, "name": "full"},
                {"camera": {"type": "custom", "eye": [100,100,100], "target": [0,0,0],
                            "zoom_extents": false}, "name": "exact_position"},
                {"camera": {"type": "standard_view", "view": "iso"}, "isolate": 12345,
                            "name": "chair_detail"}
            ],
            base_name="model_view"
        )
    """
    params: dict[str, Any] = {
        "shots": shots,
        "base_name": base_name,
        "width": width,
        "height": height,
        "transparent": transparent,
        "restore_camera": restore_camera
    }
    if output_dir:
        params["output_dir"] = output_dir
    return call_tool(ctx, "take_batch_screenshots", params, "take_batch_screenshots")


@mcp.tool()
def open_model(ctx: McpContext, path: str) -> str:
    """Open a SketchUp model file

    Args:
        path: Absolute path to the .skp file to open

    Returns success status and model information
    """
    return call_tool(ctx, "open_model", {"path": path}, "open_model")


@mcp.tool()
def save_model(ctx: McpContext, path: str | None = None) -> str:
    """Save the current SketchUp model

    Args:
        path: Optional absolute path to save to. If not provided, saves to current location

    Returns success status and saved file path
    """
    params = {"path": path} if path else {}
    return call_tool(ctx, "save_model", params, "save_model")


def main() -> None:
    """Main entry point for the server"""
    setup_logging()
    mcp.run()


if __name__ == "__main__":
    main()
