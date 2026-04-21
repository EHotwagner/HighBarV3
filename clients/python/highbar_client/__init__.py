# SPDX-License-Identifier: GPL-2.0-only
"""HighBarV3 Python client — observer + AI roles.

Generated proto stubs (`highbar/*_pb2.py`, `*_pb2_grpc.py`) are produced
by grpc_tools.protoc at dev-install time; see README.md.
"""

__version__ = "0.1.0"

SCHEMA_VERSION = "1.0.0"
"""Client-side schema version. MUST match the plugin's compile-time
constant in src/circuit/grpc/SchemaVersion.h — the Hello handshake
fails FAILED_PRECONDITION on any mismatch (FR-022a)."""
