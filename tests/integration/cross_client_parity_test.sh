#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — SC-004 cross-client parity (T093).
#
# F# and Python observers attached to the same headless match for 60s,
# streams recorded to disk, byte-equality asserted. The two clients
# MUST see byte-identical StateUpdate bytes since they read the same
# serialized shared_ptr<const string> out of the DeltaBus (data-model
# §2 invariants + SnapshotBuilder design).
#
# Exit 77 until the T104 engine-launch helper lands; the shape below
# is what the assertion will look like.

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
plugin_lib="${repo_root}/build/libSkirmishAI.so"
observer_fs="${repo_root}/clients/fsharp/samples/Observer/bin/Debug/net8.0/hb-observer"
observer_py="${repo_root}/clients/python/samples/observer.py"

if [[ ! -x "${SPRING_HEADLESS:-}" ]]; then
    echo "cross-client-parity: SPRING_HEADLESS not set — skip." >&2
    exit 77
fi
if [[ ! -f "${plugin_lib}" ]]; then
    echo "cross-client-parity: plugin .so not built — skip." >&2
    exit 77
fi
if [[ ! -x "${observer_fs}" || ! -f "${observer_py}" ]]; then
    echo "cross-client-parity: observers not built — skip." >&2
    exit 77
fi

echo "cross-client-parity: engine launch helper not wired (T104) — skip." >&2
# Shape when T104 lands:
#   1. Launch engine with the plugin + built-in AI.
#   2. In parallel: hb-observer --record fs.bin and hb-python-observer --record py.bin
#      (the --record flag lands with this test — it serializes every
#      incoming StateUpdate's raw bytes to the output file, so we can
#      compare without re-encoding.)
#   3. Stop both observers after 60s.
#   4. cmp -s fs.bin py.bin || exit 1
exit 77
