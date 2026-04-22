#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WRAPPER="$REPO_ROOT/tests/headless/itertesting.sh"
REPORTS_ROOT="$(mktemp -d)"
trap 'rm -rf "$REPORTS_ROOT"' EXIT

if [[ ! -x "$WRAPPER" ]]; then
    echo "test_itertesting_campaign: wrapper missing — fail" >&2
    exit 1
fi

run_wrapper() {
    local reports_dir="$1"
    shift
    env \
        HIGHBAR_ITERTESTING_SKIP_LIVE=true \
        HIGHBAR_ITERTESTING_REPORTS_DIR="$reports_dir" \
        "$@" \
        "$WRAPPER"
}

latest_manifest() {
    local reports_dir="$1"
    find "$reports_dir" -path '*/manifest.json' | sort | tail -n1
}

latest_stop_decision() {
    local reports_dir="$1"
    find "$reports_dir" -path '*/campaign-stop-decision.json' | sort | tail -n1
}

# Scenario 1 (US1): stalled campaign should stop early with canonical reason.
STALL_DIR="$REPORTS_ROOT/stalled"
mkdir -p "$STALL_DIR"
run_wrapper "$STALL_DIR" \
    HIGHBAR_ITERTESTING_RETRY_INTENSITY=quick \
    HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=100

stall_manifest_count="$(find "$STALL_DIR" -path '*/manifest.json' | wc -l | tr -d ' ')"
stall_decision="$(latest_stop_decision "$STALL_DIR")"
if [[ -z "$stall_decision" ]]; then
    echo "test_itertesting_campaign: missing stop decision artifact for stalled scenario" >&2
    exit 1
fi
if ! grep -q '"stop_reason": "stalled"' "$stall_decision"; then
    echo "test_itertesting_campaign: stalled scenario did not emit stop_reason=stalled" >&2
    exit 1
fi
if [[ "$stall_manifest_count" -gt 4 ]]; then
    echo "test_itertesting_campaign: stalled scenario consumed too many runs ($stall_manifest_count)" >&2
    exit 1
fi

# Scenario 2 (US2): profile envelopes should map to distinct effective retry budgets.
get_effective_runs() {
    local reports_dir="$1"
    local manifest
    manifest="$(latest_manifest "$reports_dir")"
    python3 - "$manifest" <<'PY'
import json
import sys
manifest = sys.argv[1]
with open(manifest, "r", encoding="utf-8") as f:
    payload = json.load(f)
print(payload["summary"]["effective_improvement_runs"])
PY
}

QUICK_DIR="$REPORTS_ROOT/quick"
STANDARD_DIR="$REPORTS_ROOT/standard"
DEEP_DIR="$REPORTS_ROOT/deep"
mkdir -p "$QUICK_DIR" "$STANDARD_DIR" "$DEEP_DIR"

run_wrapper "$QUICK_DIR" HIGHBAR_ITERTESTING_RETRY_INTENSITY=quick
run_wrapper "$STANDARD_DIR" HIGHBAR_ITERTESTING_RETRY_INTENSITY=standard
run_wrapper "$DEEP_DIR" HIGHBAR_ITERTESTING_RETRY_INTENSITY=deep

quick_effective="$(get_effective_runs "$QUICK_DIR")"
standard_effective="$(get_effective_runs "$STANDARD_DIR")"
deep_effective="$(get_effective_runs "$DEEP_DIR")"

if [[ "$quick_effective" -ge "$standard_effective" || "$standard_effective" -ge "$deep_effective" ]]; then
    echo "test_itertesting_campaign: retry profile envelopes not ordered (quick=$quick_effective standard=$standard_effective deep=$deep_effective)" >&2
    exit 1
fi

# Scenario 3 (US3): back-to-back campaigns should reuse and revise instruction files.
REUSE_DIR="$REPORTS_ROOT/reuse"
mkdir -p "$REUSE_DIR"
run_wrapper "$REUSE_DIR" \
    HIGHBAR_ITERTESTING_RETRY_INTENSITY=standard \
    HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=1

instr_file="$REUSE_DIR/instructions/cmd-move-unit.json"
if [[ ! -f "$instr_file" ]]; then
    echo "test_itertesting_campaign: expected instruction file missing after first campaign" >&2
    exit 1
fi
rev1="$(python3 - "$instr_file" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)
print(payload["revision"])
PY
)"

run_wrapper "$REUSE_DIR" \
    HIGHBAR_ITERTESTING_RETRY_INTENSITY=standard \
    HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=1

rev2="$(python3 - "$instr_file" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)
print(payload["revision"])
PY
)"

if [[ "$rev2" -le "$rev1" ]]; then
    echo "test_itertesting_campaign: instruction revision did not increase across campaigns ($rev1 -> $rev2)" >&2
    exit 1
fi

echo "PASS: stalled stop, profile envelopes, and instruction reuse validated"
