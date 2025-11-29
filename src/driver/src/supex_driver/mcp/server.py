import json
import logging
import os
import sys

from mcp.server import fastmcp
from mcp.server.fastmcp import Context, FastMCP

from supex_driver.connection import SketchupConnection, get_sketchup_connection

# Setup file logging for stdout and stderr
log_dir = os.path.expanduser("~/.supex/logs")
os.makedirs(log_dir, exist_ok=True)

stdout_log_file = os.path.join(log_dir, "stdout.log")
stderr_log_file = os.path.join(log_dir, "stderr.log")

# Redirect stdout to log file while preserving original
original_stdout = sys.stdout
stdout_logger = open(stdout_log_file, 'a', encoding='utf-8')

# Redirect stderr to log file while preserving original
original_stderr = sys.stderr
stderr_logger = open(stderr_log_file, 'a', encoding='utf-8')

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

# Replace sys.stdout and sys.stderr with tee streams
sys.stdout = TeeStream(original_stdout, stdout_logger)
sys.stderr = TeeStream(original_stderr, stderr_logger)

# Configure logging to stderr to avoid interfering with MCP stdio
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("supex.mcp")

# Version
__version__ = "0.3.0"
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
    resources_dir = os.path.join(os.path.dirname(__file__), "..", "..", "resources")
    file_path = os.path.join(resources_dir, "best_practices.md")
    with open(file_path, encoding='utf-8') as f:
        return f.read()


# Strategic AI guidance for SketchUp Ruby scripting
@mcp.prompt()
def ruby_scripting_strategy() -> str:
    """Provides strategic guidance for SketchUp Ruby scripting projects"""
    try:
        # Read strategy from external markdown file for easier editing
        strategy_file = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "sketchup_workflow.md")
        with open(strategy_file, encoding='utf-8') as f:
            content = f.read()
        # Remove the markdown header since it's just for file organization
        if content.startswith("# SketchUp Workflow\n\n"):
            content = content[len("# SketchUp Workflow\n\n"):]
        return content
    except Exception as e:
        logger.error(f"Failed to read sketchup_workflow.md: {e}")
        return "Error loading SketchUp workflow. Please check the sketchup_workflow.md file."


def main():
    """Main entry point for the server"""
    mcp.run()


if __name__ == "__main__":
    main()
