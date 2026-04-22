#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
FEATURE_DIR="$REPO_ROOT/specs/013-itertesting-channel-stability"

if ! command -v uv >/dev/null 2>&1; then
    echo "test_live_itertesting_hardening: uv missing — skip" >&2
    exit 77
fi

REPORTS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/highbar-itertesting-hardening.XXXXXX")"
cleanup() {
    rm -rf "$REPORTS_DIR"
}
trap cleanup EXIT

echo "test_live_itertesting_hardening: running synthetic hardened campaign"
HIGHBAR_ITERTESTING_REPORTS_DIR="$REPORTS_DIR" \
HIGHBAR_ITERTESTING_SKIP_LIVE=true \
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 \
"$HEADLESS_DIR/itertesting.sh" >/dev/null

latest_manifest="$(find "$REPORTS_DIR" -maxdepth 2 -name manifest.json | sort | tail -n 1)"
latest_report="$(find "$REPORTS_DIR" -maxdepth 2 -name run-report.md | sort | tail -n 1)"
if [[ -z "$latest_manifest" || -z "$latest_report" ]]; then
    echo "test_live_itertesting_hardening: missing manifest/report artifacts" >&2
    exit 1
fi

python3 - "$latest_manifest" "$latest_report" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
report = Path(sys.argv[2]).read_text(encoding="utf-8")

fixture_profile = manifest.get("fixture_profile") or {}
fixture_provisioning = manifest.get("fixture_provisioning") or {}
channel_health = manifest.get("channel_health") or {}
verification_rules = {
    item["command_id"]: item for item in manifest.get("verification_rules", [])
}
failure_classifications = {
    item["command_id"]: item for item in manifest.get("failure_classifications", [])
}

assert fixture_profile.get("profile_id") == "default-live-fixture-profile"
assert "builder" in fixture_profile.get("fixture_classes", [])
assert "cmd-load-units" in fixture_provisioning.get("affected_command_ids", [])
assert channel_health.get("status") == "healthy"
assert verification_rules["cmd-move-unit"]["rule_mode"] == "movement_tuned"
assert verification_rules["cmd-fight"]["rule_mode"] == "combat_tuned"
assert verification_rules["cmd-build-unit"]["rule_mode"] == "construction_tuned"
assert failure_classifications["cmd-load-units"]["primary_cause"] == "missing_fixture"
for section in (
    "## Fixture Provisioning",
    "## Channel Health",
    "## Failure Cause Summary",
):
    assert section in report, section
PY

if ! grep -Fq "HIGHBAR_STARTSCRIPT=tests/headless/scripts/minimal-slow.startscript" \
    "$FEATURE_DIR/quickstart.md"; then
    echo "test_live_itertesting_hardening: quickstart is missing the alternate-speed entrypoint" >&2
    exit 1
fi

if ! grep -Fq "Changing simulation speed for a rerun must not change the interpretation" \
    "$FEATURE_DIR/contracts/transport-adjacent-failure-classification.md"; then
    echo "test_live_itertesting_hardening: transport contract is missing alternate-speed interpretation guidance" >&2
    exit 1
fi

if [[ ! -f "$HEADLESS_DIR/scripts/minimal-slow.startscript" ]]; then
    echo "test_live_itertesting_hardening: alternate-speed startscript is missing" >&2
    exit 1
fi

if cmp -s "$HEADLESS_DIR/scripts/minimal.startscript" \
    "$HEADLESS_DIR/scripts/minimal-slow.startscript"; then
    echo "test_live_itertesting_hardening: alternate-speed startscript must differ from the default speed profile" >&2
    exit 1
fi

if ! grep -q 'channel_health' "$HEADLESS_DIR/itertesting.sh"; then
    echo "test_live_itertesting_hardening: wrapper is not keyed to manifest channel health" >&2
    exit 1
fi

echo "test_live_itertesting_hardening: running tuned-arm repro checks"
for row_id in cmd-move-unit cmd-fight cmd-build-unit; do
    "$HEADLESS_DIR/audit/repro.sh" "$row_id" --phase=live-tuned \
        --report-path="$REPORTS_DIR/${row_id}.md" >/dev/null
done

echo "PASS: live Itertesting hardening artifacts validated"
