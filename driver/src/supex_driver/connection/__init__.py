"""SketchUp and VCAD sidecar connection communication.

This module provides connection classes for communicating with the SketchUp
extension and VCAD sidecar via TCP sockets and JSON-RPC.
"""

from supex_driver.connection.sketchup_connection import (
    SketchupConnection,
    get_sketchup_connection,
)
from supex_driver.connection.sketchup_exceptions import (
    SketchUpConnectionError,
    SketchUpError,
    SketchUpProtocolError,
    SketchUpTimeoutError,
)
from supex_driver.connection.vcad_connection import (
    VCADConnection,
    get_vcad_connection,
)
from supex_driver.connection.vcad_dag import (
    ImportRef,
    VcadDag,
    VcadNode,
)
from supex_driver.connection.vcad_exceptions import (
    VCADCapabilityError,
    VCADConnectionError,
    VCADError,
    VCADProtocolError,
    VCADRemoteError,
    VCADTimeoutError,
)
from supex_driver.connection.vcad_sidecar import (
    VCADSidecar,
    get_vcad_sidecar,
)
from supex_driver.connection.vcad_viewer_relay import (
    VCADViewerCapabilityError,
    VCADViewerError,
    VCADViewerNotConnectedError,
    VCADViewerProtocolError,
    VCADViewerRelay,
    VCADViewerTimeoutError,
    get_vcad_viewer_relay,
)

__all__ = [
    "SketchupConnection",
    "get_sketchup_connection",
    "SketchUpError",
    "SketchUpConnectionError",
    "SketchUpTimeoutError",
    "SketchUpProtocolError",
    "VCADConnection",
    "get_vcad_connection",
    "VCADSidecar",
    "get_vcad_sidecar",
    "VCADError",
    "VCADConnectionError",
    "VCADTimeoutError",
    "VCADProtocolError",
    "VCADRemoteError",
    "VCADCapabilityError",
    "VCADViewerRelay",
    "get_vcad_viewer_relay",
    "VCADViewerError",
    "VCADViewerNotConnectedError",
    "VCADViewerTimeoutError",
    "VCADViewerProtocolError",
    "VCADViewerCapabilityError",
    "ImportRef",
    "VcadDag",
    "VcadNode",
]
