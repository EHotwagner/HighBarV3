# SPDX-License-Identifier: GPL-2.0-only
"""`python -m highbar_client.behavioral_coverage` entry point.

Also accepts the 004 audit mode:
`python -m highbar_client.behavioral_coverage audit [--audit-dir ...]`.
"""

from __future__ import annotations

import sys

from . import main


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
