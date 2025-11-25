"""Tests for MCP server functionality."""

from supex_driver.mcp.server import mcp


class TestMCPServer:
    """Test MCP server functionality."""

    def test_mcp_server_exists(self) -> None:
        """Test that MCP server instance exists."""
        assert mcp is not None
        assert mcp.name == "Supex"

    def test_server_has_tools(self) -> None:
        """Test that server has expected tools."""
        # Test that tools are registered by checking if decorators work
        expected_tools = [
            # Primary execution
            "eval_ruby",
            "eval_ruby_file",
            # Introspection
            "get_model_info",
            "list_entities",
            "get_selection",
            "get_layers",
            "get_materials",
            "get_camera_info",
            "take_screenshot",
            # Model management
            "open_model",
            "save_model",
            "export_scene",
            # Status and connection
            "check_sketchup_status",
            "console_capture_status",
        ]

        # Since FastMCP doesn't expose internal tools directly,
        # we test that the functions exist in the module
        from supex_driver.mcp import server

        for expected_tool in expected_tools:
            assert hasattr(server, expected_tool), f"Missing tool: {expected_tool}"


def test_version_exists() -> None:
    """Test that version is properly defined."""
    from supex_driver.mcp.server import __version__

    assert __version__ == "0.3.0"
