#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# Wrapper the ci.yml `cpp-build` job calls to produce
# libSkirmishAI.so.  Lives with the rest of the runner-setup
# helpers because it encodes the runner-specific engine layout
# (~/recoil-engine with HighBarV3 symlinked at
# AI/Skirmish/BARb).  T052.
#
# Assumes .github/runner-setup/preflight.sh has already succeeded
# and HighBarV3's source tree is already linked into the engine.
# Re-runs are idempotent — cmake --build is fine with a warm tree.

set -euo pipefail

engine_root="${HIGHBAR_ENGINE_ROOT:-$HOME/recoil-engine}"
build_dir="$engine_root/build"

[ -d "$engine_root" ] || {
    echo "build-plugin: $engine_root missing — clone BAR/Recoil first" >&2
    exit 1
}

ai_dir="$engine_root/AI/Skirmish/BARb"
if [ ! -e "$ai_dir" ]; then
    echo "build-plugin: symlinking $(pwd) -> $ai_dir"
    ln -sfn "$(pwd)" "$ai_dir"
fi

mkdir -p "$build_dir"
cd "$build_dir"

# Engine-embedded build: cmake is driven from the engine root.
if [ ! -f "$build_dir/CMakeCache.txt" ]; then
    cmake -S "$engine_root" -B "$build_dir" \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DHIGHBAR_REQUIRE_WIRE_DEPS=ON
fi

cmake --build "$build_dir" --target BARb --parallel "$(nproc)"

lib="$build_dir/AI/Skirmish/BARb/libSkirmishAI.so"
[ -f "$lib" ] || {
    echo "build-plugin: expected $lib after build but it's missing" >&2
    exit 1
}

size=$(stat -c%s "$lib")
echo "build-plugin: $lib (${size} bytes) — OK"
