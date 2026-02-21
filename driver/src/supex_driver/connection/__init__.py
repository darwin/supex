"""SketchUp and vcad sidecar connection communication.

This module provides connection classes for communicating with the SketchUp
extension and vcad sidecar via TCP sockets and JSON-RPC.
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
from supex_driver.connection.vcad_connection import (
    VcadConnection,
    get_vcad_connection,
)
from supex_driver.connection.vcad_exceptions import (
    VcadCapabilityError,
    VcadConnectionError,
    VcadError,
    VcadProtocolError,
    VcadRemoteError,
    VcadTimeoutError,
)
from supex_driver.connection.vcad_sidecar import (
    VcadSidecar,
    get_vcad_sidecar,
)
from supex_driver.connection.viewer_relay import (
    ViewerCapabilityError,
    ViewerError,
    ViewerNotConnectedError,
    ViewerProtocolError,
    ViewerRelay,
    ViewerTimeoutError,
    get_viewer_relay,
)

__all__ = [
    "SketchupConnection",
    "get_sketchup_connection",
    "SketchUpError",
    "SketchUpConnectionError",
    "SketchUpTimeoutError",
    "SketchUpProtocolError",
    "VcadConnection",
    "get_vcad_connection",
    "VcadSidecar",
    "get_vcad_sidecar",
    "VcadError",
    "VcadConnectionError",
    "VcadTimeoutError",
    "VcadProtocolError",
    "VcadRemoteError",
    "VcadCapabilityError",
    "ViewerRelay",
    "get_viewer_relay",
    "ViewerError",
    "ViewerNotConnectedError",
    "ViewerTimeoutError",
    "ViewerProtocolError",
    "ViewerCapabilityError",
]
