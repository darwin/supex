"""
SUPEX Driver: SketchUp integration through Model Context Protocol
"""

from importlib.metadata import version

__version__ = version("supex-driver")

# Re-export connection classes for convenience
from supex_driver.connection import SketchupConnection, get_sketchup_connection

__all__ = ["SketchupConnection", "get_sketchup_connection"]


def get_mcp_server():
    """Lazy import of MCP server to avoid loading logging at import time."""
    from supex_driver.mcp.server import mcp
    return mcp
