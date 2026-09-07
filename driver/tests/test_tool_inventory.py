"""Keep the documented MCP tool inventory in sync with the registered tools."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from supex_driver.mcp.mcp_server import mcp

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = {
    "guide": REPO_ROOT / "docs" / "agents" / "guide" / "mcp.md",
    "driver-readme": REPO_ROOT / "driver" / "README.md",
}
TOOL_ROW = re.compile(r"^\| `([a-z_]+)")

# Tools that only read state. Everything else mutates the model, the viewer, the
# sidecar watcher or the filesystem and must not carry readOnlyHint.
READ_ONLY_TOOLS = {
    "check_status",
    "get_camera_info",
    "get_entity",
    "get_layers",
    "get_materials",
    "get_model_info",
    "get_selection",
    "list_entities",
    "vcad_eval",
    "vcad_inspect",
    "vcad_list_nodes",
    "vcad_metrics",
    "vcad_reconcile_status",
    "vcad_viewer_state",
}


def registered_tools() -> set[str]:
    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


def mcp_section(text: str) -> str:
    """Return the text of the '## MCP Tools' section, or the whole text if absent."""
    start = text.find("\n## MCP Tools")
    if start < 0:
        return text
    end = text.find("\n## ", start + 1)
    return text[start:] if end < 0 else text[start:end]


def documented_tools(path: Path) -> set[str]:
    names = set()
    for line in mcp_section(path.read_text(encoding="utf-8")).splitlines():
        match = TOOL_ROW.match(line)
        if match:
            names.add(match.group(1))
    return names


@pytest.mark.parametrize("doc", sorted(DOCS))
def test_documented_tools_match_registered(doc: str) -> None:
    path = DOCS[doc]
    if not path.exists():
        pytest.skip(f"{path} not available in this checkout")

    registered = registered_tools()
    documented = documented_tools(path)

    missing = sorted(registered - documented)
    stale = sorted(documented - registered)
    assert not missing, f"{doc}: tools registered but undocumented: {missing}"
    assert not stale, f"{doc}: tools documented but not registered: {stale}"


def test_read_only_annotations_match_inventory() -> None:
    tools = asyncio.run(mcp.list_tools())
    annotated = {
        tool.name
        for tool in tools
        if tool.annotations is not None and tool.annotations.read_only_hint
    }
    assert annotated == READ_ONLY_TOOLS
