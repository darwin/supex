"""CLI interface for SketchUp automation.

This module provides a command-line interface for interacting with
SketchUp through the same connection layer used by the MCP server.
"""

from supex_driver.cli.main import app, main

__all__ = ["app", "main"]
