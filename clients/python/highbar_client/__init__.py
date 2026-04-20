# SPDX-License-Identifier: GPL-2.0-only
"""HighBarV3 gRPC client for Python (T084-T090).

Depends on `buf generate` output living on PYTHONPATH as the
`highbar.v1` package (see proto/buf.gen.yaml for the generator config).
"""

from .channel import Endpoint, for_endpoint, parse  # noqa: F401
from .session import SCHEMA_VERSION, hello, hello_ai, read_token_with_backoff  # noqa: F401
from .state_stream import SeqInvariantError, consume  # noqa: F401

__all__ = [
    "Endpoint",
    "for_endpoint",
    "parse",
    "SCHEMA_VERSION",
    "hello",
    "hello_ai",
    "read_token_with_backoff",
    "SeqInvariantError",
    "consume",
]
