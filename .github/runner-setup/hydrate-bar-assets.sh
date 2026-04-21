#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T048 — hydrate the minimum BAR asset set a self-hosted runner needs
# to run the acceptance grid against a live spring-headless match.
#
# Assets are pulled from the BAR CDN.  We intentionally keep the set
# small: one map (Avalanche 3.4) + the 2025-04 unit-def game archive.
# Callers wanting a different map must edit the MAPS array explicitly
# — silently growing the list would bloat every runner-setup.
#
# Idempotent: if the expected files are already present and non-empty,
# this script exits 0 without re-downloading.

set -euo pipefail

data_root="$HOME/.local/state/Beyond All Reason"

mkdir -p "$data_root/maps" "$data_root/games" "$data_root/pool"

MAPS=(
    # name                                       # url
    "Avalanche_3.4.sd7|https://maps-metadata.beyondallreason.dev/maps/Avalanche_3.4.sd7"
)

GAMES=(
    # file                                       # url
    "Beyond-All-Reason.sdz|https://content.beyondallreason.dev/game/byar-chobby.sdz"
)

download_if_missing() {
    local dest=$1 url=$2
    if [ -s "$dest" ]; then
        echo "hydrate-bar-assets: $dest present ($(stat -c%s "$dest") bytes)"
        return 0
    fi
    echo "hydrate-bar-assets: downloading $url -> $dest"
    curl -fL --retry 3 --output "$dest" "$url"
}

for entry in "${MAPS[@]}"; do
    name=${entry%%|*}
    url=${entry#*|}
    download_if_missing "$data_root/maps/$name" "$url"
done

for entry in "${GAMES[@]}"; do
    name=${entry%%|*}
    url=${entry#*|}
    download_if_missing "$data_root/games/$name" "$url"
done

# Marker so register-runner.sh can assert completion cheaply.
touch "$data_root/.highbar-assets-hydrated"
echo "hydrate-bar-assets: complete"
