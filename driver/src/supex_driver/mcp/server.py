import json
import logging
import os
import sys

from mcp.server import fastmcp
from mcp.server.fastmcp import Context, FastMCP

from supex_driver.connection import SketchupConnection, get_sketchup_connection
from supex_driver.mcp.resources import (
    find_similar_classes,
    get_docs_not_generated_message,
    get_resources_path,
    list_available_namespaces,
    list_available_pages,
    load_api_doc,
    load_api_index,
    load_namespace_index,
    load_page_doc,
    load_resource_file,
)

# Version
__version__ = "0.3.0"

# Logger instance (configured when server starts)
logger = logging.getLogger("supex.mcp")

# Flag to track if logging has been configured
_logging_configured = False


class TeeStream:
    """Stream that writes to both original stream and log file"""
    def __init__(self, original_stream, log_file):
        self.original_stream = original_stream
        self.log_file = log_file

    def write(self, data):
        self.original_stream.write(data)
        self.log_file.write(data)
        self.log_file.flush()

    def flush(self):
        self.original_stream.flush()
        self.log_file.flush()

    def __getattr__(self, name):
        return getattr(self.original_stream, name)


def setup_logging():
    """Configure logging for the MCP server.

    Sets up file logging and configures the logging format.
    Only runs once, even if called multiple times.
    """
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True

    # Setup file logging for stdout and stderr
    log_dir = os.path.expanduser("~/.supex/logs")
    os.makedirs(log_dir, exist_ok=True)

    stdout_log_file = os.path.join(log_dir, "stdout.log")
    stderr_log_file = os.path.join(log_dir, "stderr.log")

    # Redirect stdout to log file while preserving original
    stdout_logger = open(stdout_log_file, 'a', encoding='utf-8')
    stderr_logger = open(stderr_log_file, 'a', encoding='utf-8')

    # Replace sys.stdout and sys.stderr with tee streams
    sys.stdout = TeeStream(sys.stdout, stdout_logger)
    sys.stderr = TeeStream(sys.stderr, stderr_logger)

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


# Status and connection tools
@mcp.tool()
def check_sketchup_status(ctx: Context) -> str:
    """Check if SketchUp is connected and responding"""
    try:
        sketchup = get_sketchup_connection()
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
    except Exception as e:
        return json.dumps(
            {
                "status": "disconnected",
                "error": str(e),
                "message": "Make sure the SketchUp extension is running",
            }
        )


# Export functionality
@mcp.tool()
def export_scene(ctx: Context, format: str = "skp") -> str:
    """Export the current SketchUp scene

    Args:
        format: Export format (skp, obj, dae, stl, png, jpg)
    """
    try:
        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="export", params={"format": format}, request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# Ruby code evaluation
@mcp.tool()
def eval_ruby(ctx: Context, code: str) -> str:
    """Evaluate arbitrary Ruby code in SketchUp context

    Args:
        code: Ruby code to execute
    """
    try:
        logger.info(f"Evaluating Ruby code ({len(code)} characters)")

        sketchup = get_sketchup_connection()

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
    except Exception as e:
        logger.error(f"Error evaluating Ruby code: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


# Console capture functionality
@mcp.tool()
def console_capture_status(ctx: Context) -> str:
    """Get console capture status and log file information"""
    try:
        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="console_capture_status", params={}, request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# File-based Ruby evaluation tools
@mcp.tool()
def eval_ruby_file(ctx: Context, file_path: str) -> str:
    """Evaluate Ruby code from a file in SketchUp context

    Args:
        file_path: Absolute path to Ruby file to execute
    """
    try:
        logger.info(f"Evaluating Ruby file: {file_path}")

        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="eval_ruby_file",
            params={"file_path": file_path},
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error evaluating Ruby file: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


# Introspection tools
@mcp.tool()
def get_model_info(ctx: Context) -> str:
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
    try:
        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="get_model_info",
            params={},
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error getting model info: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def list_entities(ctx: Context, entity_type: str = "all") -> str:
    """List entities in the model

    Args:
        entity_type: Type to filter - one of: faces, edges, groups, components, all

    Returns list of entities with type, name, and layer information
    """
    try:
        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="list_entities",
            params={"entity_type": entity_type},
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error listing entities: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_selection(ctx: Context) -> str:
    """Get currently selected entities in SketchUp

    Returns:
    - count: Number of selected entities
    - entities: List of selected entities with details (type, properties)
    """
    try:
        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="get_selection",
            params={},
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error getting selection: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_layers(ctx: Context) -> str:
    """Get list of layers (tags) in the model

    Returns list of layers with name, visible state, and entity count
    """
    try:
        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="get_layers",
            params={},
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error getting layers: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_materials(ctx: Context) -> str:
    """Get list of materials in the model

    Returns list of materials with name, color, and texture information
    """
    try:
        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="get_materials",
            params={},
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error getting materials: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_camera_info(ctx: Context) -> str:
    """Get current camera position and settings

    Returns camera eye position, target, up vector, and field of view
    """
    try:
        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="get_camera_info",
            params={},
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error getting camera info: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def take_screenshot(
    ctx: Context,
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
    try:
        sketchup = get_sketchup_connection()
        params = {
            "width": width,
            "height": height,
            "transparent": transparent
        }
        if output_path:
            params["output_path"] = output_path

        result = sketchup.send_command(
            method="take_screenshot",
            params=params,
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error taking screenshot: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def open_model(ctx: Context, path: str) -> str:
    """Open a SketchUp model file

    Args:
        path: Absolute path to the .skp file to open

    Returns success status and model information
    """
    try:
        sketchup = get_sketchup_connection()
        result = sketchup.send_command(
            method="open_model",
            params={"path": path},
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error opening model: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def save_model(ctx: Context, path: str | None = None) -> str:
    """Save the current SketchUp model

    Args:
        path: Optional absolute path to save to. If not provided, saves to current location

    Returns success status and saved file path
    """
    try:
        sketchup = get_sketchup_connection()
        params = {"path": path} if path else {}
        result = sketchup.send_command(
            method="save_model",
            params=params,
            request_id=ctx.request_id
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error saving model: {str(e)}")
        return json.dumps({"success": False, "error": str(e)})


# MCP Resources - documentation accessible to MCP clients
@mcp.resource("supex://docs/best-practices")
def best_practices_resource() -> str:
    """Best practices for SketchUp modeling learned from real projects"""
    content = load_resource_file("best_practices.md")
    if content:
        return content
    return "Error: best_practices.md not found"


@mcp.resource("supex://docs/index")
def docs_index_resource() -> str:
    """Documentation index - start here to discover available resources"""
    content = load_resource_file("index.md")
    if content:
        return content
    return "Error: index.md not found"


@mcp.resource("supex://docs/workflow")
def workflow_resource() -> str:
    """Complete SketchUp workflow guide for Ruby scripting"""
    content = load_resource_file("workflow.md")
    if content:
        # Remove the markdown header since it's just for file organization
        if content.startswith("# SketchUp Workflow\n\n"):
            content = content[len("# SketchUp Workflow\n\n"):]
        # Inject absolute path to SketchUp API documentation
        api_path = str(get_resources_path() / "docs" / "api")
        content = content.replace("{SKETCHUP_DOCS_PATH}", api_path)
        return content
    return "Error: workflow.md not found"


@mcp.resource("supex://docs/api/index")
def api_index_resource() -> str:
    """Lightweight API overview with Quick Reference and namespace summaries (~3k tokens).

    For detailed namespace documentation, use:
    - supex://docs/api/Geom/index - Geometry classes (~3k tokens)
    - supex://docs/api/Sketchup/index - SketchUp modeling classes (~8k tokens)
    """
    content = load_api_index()
    if content:
        return content
    return get_docs_not_generated_message()


@mcp.resource("supex://docs/api/{namespace}/index")
def namespace_index_resource(namespace: str) -> str:
    """Namespace-specific API index with categorized class listings.

    Available namespaces:
    - supex://docs/api/Geom/index - Points, vectors, transformations (~3k tokens)
    - supex://docs/api/Sketchup/index - Model, entities, materials (~8k tokens)
    """
    content = load_namespace_index(namespace)
    if content:
        return content

    # Check if API docs exist at all
    api_path = get_resources_path() / "docs" / "api"
    if not api_path.exists():
        return get_docs_not_generated_message()

    # Docs exist but namespace not found - provide helpful suggestions
    available = list_available_namespaces()
    error_msg = f"# Namespace Index Not Found\n\nNo index found for namespace: `{namespace}`\n\n"
    if available:
        error_msg += "**Available namespace indexes:**\n"
        for ns in available:
            error_msg += f"- `supex://docs/api/{ns}/index`\n"
    else:
        error_msg += "Use `supex://docs/api/index` for the main API overview."
    return error_msg


@mcp.resource("supex://docs/api/{class_name}")
def api_class_resource(class_name: str) -> str:
    """API documentation for a specific SketchUp class.

    Uses Ruby syntax for namespaced classes:
    - supex://docs/api/Sketchup::Face
    - supex://docs/api/Geom::Point3d
    - supex://docs/api/Array
    """
    # Convert Ruby namespace syntax (::) to path (/)
    class_path = class_name.replace("::", "/")

    content = load_api_doc(class_path)
    if content:
        return content

    # Check if API docs exist at all
    api_path = get_resources_path() / "docs" / "api"
    if not api_path.exists():
        return get_docs_not_generated_message()

    # Docs exist but class not found - provide helpful suggestions
    similar = find_similar_classes(class_path)
    error_msg = f"# Documentation Not Found\n\nNo documentation found for: `{class_name}`\n\n"
    if similar:
        error_msg += "**Similar classes:**\n"
        for cls in similar:
            # Convert back to Ruby syntax for display
            ruby_name = cls.replace("/", "::")
            error_msg += f"- `supex://docs/api/{ruby_name}`\n"
    else:
        error_msg += "Use `supex://docs/api/index` to see all available documentation."
    return error_msg


@mcp.resource("supex://docs/quick-reference")
def quick_reference_resource() -> str:
    """Quick reference for most used SketchUp classes and entry points"""
    content = load_resource_file("quick_reference.md")
    if content:
        return content
    return "Error: quick_reference.md not found"


@mcp.resource("supex://docs/pages/{page_name}")
def pages_resource(page_name: str) -> str:
    """Tutorial and guide pages for SketchUp Ruby API.

    Available pages:
    - supex://docs/pages/generating_geometry
    - supex://docs/pages/importer_options
    - supex://docs/pages/exporter_options
    """
    content = load_page_doc(page_name)
    if content:
        return content

    # Check if pages directory exists
    api_path = get_resources_path() / "docs" / "api" / "pages"
    if not api_path.exists():
        return get_docs_not_generated_message()

    # Pages exist but requested page not found
    available = list_available_pages()
    error_msg = f"# Page Not Found\n\nNo page found: `{page_name}`\n\n"
    if available:
        error_msg += "**Available pages:**\n"
        for page in available:
            error_msg += f"- `supex://docs/pages/{page}`\n"
    return error_msg


def main():
    """Main entry point for the server"""
    setup_logging()
    mcp.run()


if __name__ == "__main__":
    main()
