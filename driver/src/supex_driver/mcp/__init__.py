"""MCP server for SketchUp automation."""

__all__ = ["mcp", "main"]


def __getattr__(name: str):
    """Lazy import to avoid loading server module at package import time.

    This prevents logging configuration from running when importing
    submodules like supex_driver.mcp.resources.
    """
    if name in ("mcp", "main"):
        from supex_driver.mcp.server import main, mcp
        if name == "mcp":
            return mcp
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
