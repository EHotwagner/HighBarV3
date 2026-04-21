#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T050 — preflight check for bar-engine-labeled jobs.  Runs at the
# head of every self-hosted CI step and fails loudly (exit 1, NOT
# exit 77) if the engine binary or asset cache is missing.
#
# Rationale: a missing binary on a bar-engine runner is a provisioning
# bug, not an acceptable skip — research.md §R2 and
# contracts/ci-skip-reason.md §Scope both insist CI reports "runner
# broken" as a failure, never a silent pass.

set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../.." && pwd)
pin_file="$repo_root/data/config/spring-headless.pin"

[ -f "$pin_file" ] || {
    echo "preflight: $pin_file missing" >&2
    exit 1
}

get_field() {
    awk -v k="$1" '
        $1==k && $2=="=" {
            sub(/^[^=]+=[[:space:]]*/, "")
            gsub(/^"|"$/, "")
            print; exit
        }
    ' "$pin_file"
}

release_id=$(get_field release_id)
sha256_expected=$(get_field sha256)
install_rel=$(get_field install_path_relative)

for v in release_id sha256_expected install_rel; do
    [ -n "${!v}" ] || { echo "preflight: empty pin field '$v'" >&2; exit 1; }
done

binary="$HOME/.local/state/$install_rel/spring-headless"
if [ ! -x "$binary" ]; then
    echo "preflight: $binary missing — run install-spring-headless.sh on this runner" >&2
    exit 1
fi

actual=$(sha256sum "$binary" | awk '{print $1}')
if [ "$actual" != "$sha256_expected" ]; then
    echo "preflight: $binary SHA mismatch (have $actual, want $sha256_expected for $release_id)" >&2
    exit 1
fi

marker="$HOME/.local/state/Beyond All Reason/.highbar-assets-hydrated"
if [ ! -f "$marker" ]; then
    echo "preflight: BAR asset cache marker missing — run hydrate-bar-assets.sh" >&2
    exit 1
fi

# Minimum files every acceptance script assumes.  If these are
# individually missing the grid will fail much later in a confusing
# way — catch it here.
required=(
    "$HOME/.local/state/Beyond All Reason/maps/Avalanche_3.4.sd7"
    "$HOME/.local/state/Beyond All Reason/games/Beyond-All-Reason.sdz"
)
for f in "${required[@]}"; do
    if [ ! -s "$f" ]; then
        echo "preflight: required asset missing or empty: $f" >&2
        exit 1
    fi
done

# tooling used by the acceptance grid
for tool in curl cmake ctest bash awk grep jq python3; do
    command -v "$tool" >/dev/null || {
        echo "preflight: $tool not on PATH" >&2
        exit 1
    }
done

echo "preflight: $release_id binary OK, asset cache hydrated ($(ls "$HOME/.local/state/Beyond All Reason/maps" | wc -l) maps, $(ls "$HOME/.local/state/Beyond All Reason/games" | wc -l) games)"
