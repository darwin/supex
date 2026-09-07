"""Every sidecar tool the driver calls must have a dispatch arm in the sidecar.

The driver talks to the VCAD sidecar over JSON-RPC ``tools/call`` and the sidecar
dispatches on the tool name with a Rust ``match``. Nothing at build time ties the
two together, so a tool added on the driver side alone fails only at runtime with
"Unknown tool". This test compares the names used in ``vcad_connection.py`` with
the match arms in ``server.rs``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER_CONNECTION = REPO_ROOT / "driver" / "src" / "supex_driver" / "connection" / "vcad_connection.py"
SIDECAR_SERVER = REPO_ROOT / "vcad" / "sidecar" / "src" / "server.rs"

DRIVER_CALL = re.compile(r'send_command\(\s*"(vcad\.[a-z_]+)"')
SIDECAR_ARM = re.compile(r'^\s*"(vcad\.[a-z_]+)"\s*=>', re.MULTILINE)


def driver_tools() -> set[str]:
    return set(DRIVER_CALL.findall(DRIVER_CONNECTION.read_text(encoding="utf-8")))


def sidecar_tools() -> set[str]:
    return set(SIDECAR_ARM.findall(SIDECAR_SERVER.read_text(encoding="utf-8")))


def test_driver_tools_are_dispatched_by_sidecar() -> None:
    if not SIDECAR_SERVER.exists():
        pytest.skip(f"{SIDECAR_SERVER} not available in this checkout")

    called = driver_tools()
    dispatched = sidecar_tools()
    assert called, "no sidecar tool calls found in the driver; the regex is probably stale"
    assert dispatched, "no dispatch arms found in the sidecar; the regex is probably stale"

    missing = sorted(called - dispatched)
    unused = sorted(dispatched - called)
    assert not missing, f"driver calls sidecar tools without a dispatch arm: {missing}"
    assert not unused, f"sidecar dispatches tools the driver never calls: {unused}"
