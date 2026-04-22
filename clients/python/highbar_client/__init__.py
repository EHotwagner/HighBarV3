# SPDX-License-Identifier: GPL-2.0-only
"""HighBarV3 Python client — observer + AI roles.

Generated proto stubs (`highbar/*_pb2.py`, `*_pb2_grpc.py`) are produced
by grpc_tools.protoc at dev-install time; see README.md.
"""

import os as _os
import sys as _sys

# Generated stubs use absolute `from highbar import common_pb2` imports.
# Make the `highbar/` subpackage importable as a top-level name so those
# resolve at runtime (parity with the conftest.py trick used in tests).
# Idempotent — only inserted once per interpreter.
_pkg_dir = _os.path.dirname(__file__)
if _pkg_dir not in _sys.path:
    _sys.path.insert(0, _pkg_dir)

__version__ = "0.1.0"

SCHEMA_VERSION = "1.0.0"
"""Client-side schema version. MUST match the plugin's compile-time
constant in src/circuit/grpc/SchemaVersion.h — the Hello handshake
fails FAILED_PRECONDITION on any mismatch (FR-022a)."""
