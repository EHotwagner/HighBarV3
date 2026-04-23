#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Resolve row-specific unit prerequisites for the live audit harness.

When a row depends on a known unit type, this helper returns the expected
unit name so reviewers can feed it into live setup steps consistently.
Fallback mode still prints the requested unit name so the harness remains
runnable when a row has no curated prerequisite mapping.
"""

from __future__ import annotations

import argparse


ROW_PREREQUISITES = {
    "cmd-build-unit": ("armmex",),
    "cmd-move-unit": ("armflash",),
    "cmd-fight": ("armflash",),
    "cmd-patrol": ("armflash",),
    "cmd-attack": ("armflash",),
    "cmd-load-units": ("armflash", "armatlas", "armhvytrans"),
    "cmd-load-onto": ("armflash", "armatlas", "armhvytrans"),
    "cmd-load-units-area": ("armflash", "armatlas", "armhvytrans"),
    "cmd-unload-unit": ("armatlas", "armhvytrans"),
    "cmd-unload-units-area": ("armatlas", "armhvytrans"),
    "rpc-save": ("armcom",),
    "rpc-load": ("armcom",),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--all", action="store_true", help="print all prerequisite units for a row")
    args = parser.parse_args()
    units = ROW_PREREQUISITES.get(args.target, (args.target,))
    if args.all:
        print("\n".join(units))
    else:
        print(units[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
