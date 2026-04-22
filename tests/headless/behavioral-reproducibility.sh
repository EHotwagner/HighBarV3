#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# T032 [US6] — Five-run reproducibility gate.
#
# Invokes `aicommand-behavioral-coverage.sh` 5× with run-indexed output
# directories, compares the 5 `.digest` files byte-for-byte, and
# asserts the p50 framerate spread across runs is ≤ 5% (FR-009).
#
# Expected wall-clock: ≤ 25 minutes on the reference host. Runs only on
# self-hosted runners (spec §Assumptions); hosted GitHub runners skip
# via the 77 prereq-missing exit code.
#
# Exit codes (per quickstart.md §6):
#   0  — all 5 digests byte-identical AND framerate spread ≤ 5%.
#   1  — digest mismatch (prints per-row diff of critical columns); OR
#        framerate spread > 5%.
#   77 — any constituent run returned 77 (setup skip).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"

COVERAGE_SH="$HEADLESS_DIR/aicommand-behavioral-coverage.sh"
REPORT_CLI=(uv run --project "$REPO_ROOT/clients/python" python -m \
    highbar_client.behavioral_coverage.report)

if [[ ! -x "$COVERAGE_SH" ]]; then
    echo "behavioral-reproducibility: aicommand-behavioral-coverage.sh missing — skip" >&2
    exit 77
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "behavioral-reproducibility: uv missing — skip" >&2
    exit 77
fi

RUN_DIR="${HIGHBAR_RUN_DIR:-/tmp/hb-run}"
OUTPUT_ROOT="${HIGHBAR_OUTPUT_DIR:-$REPO_ROOT/build/reports}"
ENGINE_LOG="$RUN_DIR/highbar-launch.log"

declare -a digest_files
declare -a framerates

for N in 1 2 3 4 5; do
    echo "[behavioral-reproducibility] run $N/5"
    out="$OUTPUT_ROOT/run-$N"
    mkdir -p "$out"

    "$COVERAGE_SH" --output-dir "$out" --run-index "$N"
    rc=$?
    if [[ $rc -eq 77 ]]; then
        echo "[behavioral-reproducibility] run $N skipped (rc=77) — skip entire reproducibility gate" >&2
        exit 77
    elif [[ $rc -ne 0 && $rc -ne 1 ]]; then
        # 0 = PASS, 1 = threshold-miss (still measurable). Anything
        # else is an internal bug — abort.
        echo "[behavioral-reproducibility] run $N failed rc=$rc — abort" >&2
        exit 1
    fi

    digest="$out/run-$N/aicommand-behavioral-coverage.digest"
    # The driver emits under --output-dir/run-N when --run-index is
    # set, so fold the path accordingly.
    if [[ ! -f "$digest" ]]; then
        digest="$out/aicommand-behavioral-coverage.digest"
    fi
    if [[ ! -f "$digest" ]]; then
        echo "[behavioral-reproducibility] missing digest for run $N — fail" >&2
        exit 1
    fi
    digest_files+=("$digest")

    # p50 framerate extraction — reuse us1-framerate.sh's regex shape.
    if [[ -f "$ENGINE_LOG" ]]; then
        p50=$(grep -oE 'p50_fps=[0-9.]+' "$ENGINE_LOG" | tail -1 \
              | sed 's/.*=//')
        framerates+=("${p50:-0}")
    else
        framerates+=("0")
    fi

    echo "[behavioral-reproducibility] run $N verified $(cat "$digest" | head -c 16)… framerate_p50=${framerates[-1]}"
done

# ---- digest comparison --------------------------------------------------

first="${digest_files[0]}"
mismatch_idx=0
for i in "${!digest_files[@]}"; do
    if ! cmp -s "$first" "${digest_files[$i]}"; then
        mismatch_idx=$((i + 1))
        echo "[behavioral-reproducibility] digest mismatch between run 1 and run $mismatch_idx" >&2
        # Localize: diff the critical columns via report --diff.
        first_csv="${first%.digest}.csv"
        differ_csv="${digest_files[$i]%.digest}.csv"
        "${REPORT_CLI[@]}" diff "$first_csv" "$differ_csv" >&2 || true
        exit 1
    fi
done

echo "[behavioral-reproducibility] all 5 digests identical"

# ---- framerate spread --------------------------------------------------

# Build a sorted numeric list.
sorted=$(printf '%s\n' "${framerates[@]}" | sort -n)
min=$(echo "$sorted" | head -1)
max=$(echo "$sorted" | tail -1)
# Compute median via awk (sort already ascending).
count=${#framerates[@]}
median=$(echo "$sorted" | awk -v c="$count" 'NR==int((c+1)/2){print}')

# Spread = (max - min) / median.
spread=$(awk -v mx="$max" -v mn="$min" -v md="$median" \
    'BEGIN { if (md > 0) print (mx - mn) / md; else print 1.0 }')
pct=$(awk -v s="$spread" 'BEGIN { print s * 100.0 }')

echo "[behavioral-reproducibility] framerate p50 samples: ${framerates[*]}"
echo "[behavioral-reproducibility] spread=${pct}% (≤5% required)"

over=$(awk -v s="$spread" 'BEGIN { print (s > 0.05) ? 1 : 0 }')
if [[ "$over" -eq 1 ]]; then
    echo "[behavioral-reproducibility] framerate spread > 5% — fail" >&2
    exit 1
fi

echo "behavioral-reproducibility: PASS"
