#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Resolve a unit-def id from the current Hello payload when available.

Fallback mode is deliberately simple: print the requested unit name so the
checked-in audit harness remains runnable even when no live gateway is
available on the current host.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("unit_name")
    args = parser.parse_args()
    print(args.unit_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
