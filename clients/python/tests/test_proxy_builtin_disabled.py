# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_circuit_builtin_behavior_is_permanently_disabled():
    header = (REPO_ROOT / "src/circuit/CircuitAI.h").read_text(encoding="utf-8")
    source = (REPO_ROOT / "src/circuit/CircuitAI.cpp").read_text(encoding="utf-8")

    assert "bool enableBuiltin = false;" in header
    assert "enableBuiltin = StringToBool" not in source
    assert "enable_builtin=true ignored" in source


def test_public_option_and_launcher_cannot_reenable_builtin_behavior():
    ai_options = (REPO_ROOT / "data/AIOptions.lua").read_text(encoding="utf-8")
    launcher = (REPO_ROOT / "tests/headless/_launch.sh").read_text(encoding="utf-8")

    option_block = ai_options[ai_options.index("key     = 'enable_builtin'") :]
    option_block = option_block[: option_block.index("\n\t{ -- list")]

    assert "def     = false" in option_block
    assert 'export HIGHBAR_ENABLE_BUILTIN="false"' in launcher
    assert 'export HIGHBAR_ENABLE_BUILTIN="true"' not in launcher
