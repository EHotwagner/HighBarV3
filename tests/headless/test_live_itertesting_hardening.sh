#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
FEATURE_DIR="$REPO_ROOT/specs/014-fixture-bootstrap-simplification"

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
class_statuses = {
    item["fixture_class"]: item for item in fixture_provisioning.get("class_statuses", [])
}
shared_instances = fixture_provisioning.get("shared_fixture_instances", [])

assert fixture_profile.get("profile_id") == "default-live-fixture-profile"
assert "builder" in fixture_profile.get("fixture_classes", [])
assert "cmd-load-units" in fixture_provisioning.get("affected_command_ids", [])
assert channel_health.get("status") == "healthy"
assert verification_rules["cmd-move-unit"]["rule_mode"] == "movement_tuned"
assert verification_rules["cmd-fight"]["rule_mode"] == "combat_tuned"
assert verification_rules["cmd-build-unit"]["rule_mode"] == "construction_tuned"
assert failure_classifications["cmd-load-units"]["primary_cause"] == "missing_fixture"
assert class_statuses["transport_unit"]["status"] == "missing"
assert "cmd-load-units" in class_statuses["transport_unit"]["affected_command_ids"]
assert any(item["fixture_class"] == "commander" for item in shared_instances)
for section in (
    "## Fixture Provisioning",
    "## Command Semantic Inventory",
    "## Channel Health",
    "## Failure Cause Summary",
    "### Fixture Class Statuses",
):
    assert section in report, section
assert "`32102` `MANUAL_LAUNCH`" in report
assert "`37382` `WANT_CLOAK`" in report
assert "simplified bootstrap" not in report.lower()
PY

SEMANTIC_DIR="$REPORTS_DIR/semantic"
mkdir -p "$SEMANTIC_DIR"
uv run --project "$REPO_ROOT/clients/python" python - "$SEMANTIC_DIR" <<'PY'
import sys
from pathlib import Path

from highbar_client.behavioral_coverage.itertesting_runner import build_run, write_run_bundle
from highbar_client.behavioral_coverage.registry import REGISTRY

reports_dir = Path(sys.argv[1])
run = build_run(
    campaign_id="semantic-gates",
    sequence_index=0,
    reports_dir=reports_dir,
    live_rows=[
        {
            "arm_name": "set_wanted_max_speed",
            "category": REGISTRY["set_wanted_max_speed"].category,
            "dispatched": "false",
            "verified": "false",
            "evidence": "emprework mod option disabled for wanted-speed validation",
            "error": "precondition_unmet",
        },
        {
            "arm_name": "dgun",
            "category": REGISTRY["dgun"].category,
            "dispatched": "false",
            "verified": "false",
            "evidence": "non-commander manual launch substitution (32102) means this unit does not receive the command descriptor",
            "error": "precondition_unmet",
        },
        {
            "arm_name": "attack",
            "category": REGISTRY["attack"].category,
            "dispatched": "true",
            "verified": "false",
            "evidence": "place_target_on_ground Lua rewrite converted the unit target into map coordinates",
            "error": "effect_not_observed",
        },
        {
            "arm_name": "load_units",
            "category": REGISTRY["load_units"].category,
            "dispatched": "false",
            "verified": "false",
            "evidence": "transport fixture refresh_failed after payload stale event",
            "error": "precondition_unmet",
        },
    ],
)
write_run_bundle(run, reports_dir)
PY

semantic_manifest="$(find "$SEMANTIC_DIR" -maxdepth 2 -name manifest.json | sort | tail -n 1)"
semantic_report="$(find "$SEMANTIC_DIR" -maxdepth 2 -name run-report.md | sort | tail -n 1)"
python3 - "$semantic_manifest" "$semantic_report" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
report = Path(sys.argv[2]).read_text(encoding="utf-8")
semantic_gates = {item["command_id"]: item for item in manifest.get("semantic_gates", [])}
fixture = manifest.get("fixture_provisioning") or {}
class_statuses = {item["fixture_class"]: item for item in fixture.get("class_statuses", [])}

assert semantic_gates["cmd-set-wanted-max-speed"]["gate_kind"] == "mod-option"
assert semantic_gates["cmd-dgun"]["gate_kind"] == "unit-shape"
assert semantic_gates["cmd-dgun"]["custom_command_id"] == 32102
assert semantic_gates["cmd-attack"]["gate_kind"] == "lua-rewrite"
assert class_statuses["transport_unit"]["status"] == "unusable"
assert "## Semantic Gates" in report
assert "custom command id: 32102" in report
PY

if ! grep -Fq "Three consecutive prepared live closeout runs complete with healthy channel status" \
    "$FEATURE_DIR/quickstart.md"; then
    echo "test_live_itertesting_hardening: quickstart is missing the prepared rerun guidance" >&2
    exit 1
fi

if ! grep -Fq "simplified bootstrap blocker" \
    "$FEATURE_DIR/contracts/fixture-blocker-classification-and-reporting.md"; then
    echo "test_live_itertesting_hardening: 014 blocker-reporting contract is missing the legacy blocker removal guidance" >&2
    exit 1
fi

if ! grep -q 'semantic_inventory' "$HEADLESS_DIR/itertesting.sh"; then
    echo "test_live_itertesting_hardening: wrapper is not keyed to semantic inventory output" >&2
    exit 1
fi

echo "test_live_itertesting_hardening: running tuned-arm repro checks"
for row_id in cmd-move-unit cmd-fight cmd-build-unit; do
    "$HEADLESS_DIR/audit/repro.sh" "$row_id" --phase=live-tuned \
        --report-path="$REPORTS_DIR/${row_id}.md" >/dev/null
done

echo "PASS: live Itertesting hardening artifacts validated"
