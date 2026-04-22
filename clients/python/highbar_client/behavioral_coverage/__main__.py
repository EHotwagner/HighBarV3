# SPDX-License-Identifier: GPL-2.0-only
"""`python -m highbar_client.behavioral_coverage` entry point (FR-013)."""

from __future__ import annotations

import sys

from . import main


if __name__ == "__main__":
    sys.exit(main())
