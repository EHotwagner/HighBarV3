#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T047 — install the pinned spring-headless binary on a self-hosted
# runner.  Reads data/config/spring-headless.pin, downloads via
# acquisition_url, verifies SHA256, installs into
#   $HOME/.local/state/Beyond All Reason/engine/<release_id>/spring-headless
#
# Idempotent: if the target binary already matches the pinned SHA256,
# exits 0 without re-downloading.
#
# Exits non-zero (1) if the checksum mismatches or the download fails.
# No exit-77 semantics here — this runs out-of-band of the test grid.

set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../.." && pwd)
pin_file="$repo_root/data/config/spring-headless.pin"

[ -f "$pin_file" ] || {
    echo "install-spring-headless: missing $pin_file" >&2
    exit 1
}

# Minimal TOML reader — the pin file is hand-authored, no arrays, no tables
# beyond [engine].  key = "val" is all we need.
get_field() {
    local key=$1
    awk -v k="$key" '
        $1==k && $2=="=" {
            sub(/^[^=]+=[[:space:]]*/, "")
            gsub(/^"|"$/, "")
            print
            exit
        }
    ' "$pin_file"
}

release_id=$(get_field release_id)
sha256_expected=$(get_field sha256)
acquisition_url=$(get_field acquisition_url)
install_rel=$(get_field install_path_relative)

for v in release_id sha256_expected acquisition_url install_rel; do
    [ -n "${!v}" ] || {
        echo "install-spring-headless: empty field '$v' in pin" >&2
        exit 1
    }
done

install_dir="$HOME/.local/state/$install_rel"
binary="$install_dir/spring-headless"

if [ -x "$binary" ]; then
    actual=$(sha256sum "$binary" | awk '{print $1}')
    if [ "$actual" = "$sha256_expected" ]; then
        echo "install-spring-headless: $binary already matches pin ($release_id)"
        exit 0
    fi
    echo "install-spring-headless: existing binary sha mismatch (have $actual, want $sha256_expected); reinstalling" >&2
fi

mkdir -p "$install_dir"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

archive="$tmp/spring-headless.7z"
echo "install-spring-headless: downloading $acquisition_url"
curl -fL --retry 3 --output "$archive" "$acquisition_url"

command -v 7z >/dev/null || {
    echo "install-spring-headless: 7z not on PATH; install p7zip" >&2
    exit 1
}

(cd "$tmp" && 7z x -y "$archive" >/dev/null)

# The archive layout puts spring-headless at the archive root (BAR
# minimal-portable tarball convention).
src_bin=$(find "$tmp" -maxdepth 3 -name spring-headless -type f -print -quit)
[ -n "$src_bin" ] || {
    echo "install-spring-headless: spring-headless not found inside archive" >&2
    exit 1
}

actual=$(sha256sum "$src_bin" | awk '{print $1}')
if [ "$actual" != "$sha256_expected" ]; then
    echo "install-spring-headless: SHA256 mismatch after extract (have $actual, want $sha256_expected)" >&2
    exit 1
fi

install -m 0755 "$src_bin" "$binary"
# Copy sibling runtime libraries if the portable tarball shipped them.
src_dir=$(dirname "$src_bin")
if [ -d "$src_dir" ]; then
    find "$src_dir" -maxdepth 1 -type f \( -name '*.so*' -o -name 'spring-dedicated' \) -print0 \
        | xargs -0 -I{} install -m 0644 {} "$install_dir/" 2>/dev/null || true
fi

echo "install-spring-headless: installed $binary ($release_id)"
