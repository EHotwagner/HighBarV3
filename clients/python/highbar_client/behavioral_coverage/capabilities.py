# SPDX-License-Identifier: GPL-2.0-only
"""Capability vocabulary for the behavioral-coverage macro driver.

Closed set — adding a new tag requires a matching BootstrapStep in
`bootstrap.py`. See contracts/arm-registry.md §Required-capability
vocabulary and contracts/bootstrap-plan.md for the mapping from tag
to provisioning unit-def on the default `minimal.startscript`.
"""

from __future__ import annotations

from typing import Final, Literal

CAPABILITY_TAGS: Final[tuple[str, ...]] = (
    "commander",
    "mex",
    "solar",
    "radar",
    "factory_ground",
    "factory_air",
    "builder",
    "cloakable",
    "none",
)

Capability = Literal[
    "commander",
    "mex",
    "solar",
    "radar",
    "factory_ground",
    "factory_air",
    "builder",
    "cloakable",
    "none",
]


def is_valid_capability(tag: str) -> bool:
    """True iff ``tag`` is a member of the closed vocabulary."""
    return tag in CAPABILITY_TAGS
