"""SketchUp connection communication.

This module provides the SketchupConnection class for communicating
with the SketchUp extension via TCP sockets and JSON-RPC.
"""

from supex_driver.connection.connection import (
    SketchupConnection,
    get_sketchup_connection,
)
from supex_driver.connection.exceptions import (
    SketchUpConnectionError,
    SketchUpError,
    SketchUpProtocolError,
    SketchUpTimeoutError,
)

__all__ = [
    "SketchupConnection",
    "get_sketchup_connection",
    "SketchUpError",
    "SketchUpConnectionError",
    "SketchUpTimeoutError",
    "SketchUpProtocolError",
]
