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

assert_wrapper_semantic_inventory() {
    local reports_dir="$1"
    local output
    output="$(run_wrapper "$reports_dir" HIGHBAR_ITERTESTING_RETRY_INTENSITY=quick)"
    if [[ "$output" != *"semantic_inventory=32102:MANUAL_LAUNCH@cmd_manual_launch.lua"* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit semantic inventory" >&2
        exit 1
    fi
    if [[ "$output" != *"transport_status="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit transport status" >&2
        exit 1
    fi
    if [[ "$output" != *"bootstrap_readiness="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit bootstrap readiness" >&2
        exit 1
    fi
    if [[ "$output" != *"callback_diagnostics="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit callback diagnostics" >&2
        exit 1
    fi
    if [[ "$output" != *"runtime_capability_profile="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit runtime capability profile" >&2
        exit 1
    fi
    if [[ "$output" != *"map_source_decisions="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit map source summary" >&2
        exit 1
    fi
    if [[ "$output" != *"fully_interpreted="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit fully_interpreted state" >&2
        exit 1
    fi
    if [[ "$output" != *"interpretation_warnings="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit interpretation warnings" >&2
        exit 1
    fi
    if [[ "$output" != *"decision_trace="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit decision trace summary" >&2
        exit 1
    fi
    if [[ "$output" != *"prerequisite_resolution="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit prerequisite resolution" >&2
        exit 1
    fi
    if [[ "$output" != *"semantic_gates="* ]]; then
        echo "test_itertesting_campaign: wrapper did not emit semantic gate summary" >&2
        exit 1
    fi
}

assert_split_live_setup_sequences_smoke_then_seeded() {
    local tmpdir
    local output
    tmpdir="$(mktemp -d)"
    output="$(
        WRAPPER="$WRAPPER" \
        HIGHBAR_ITERTESTING_SKIP_LIVE=false \
        HIGHBAR_ITERTESTING_SPLIT_LIVE_SETUP=true \
        HIGHBAR_ITERTESTING_REPORTS_DIR="$tmpdir/reports" \
        HIGHBAR_RUN_DIR="$tmpdir/run" \
        HIGHBAR_WRITE_DIR="$tmpdir/write" \
        bash -lc '
            set -euo pipefail
            source "$WRAPPER"
            launch_live_topology() { echo "launch:$1"; return 0; }
            run_natural_smoke_campaign() { echo "smoke"; return 0; }
            run_live_campaign() { echo "main:$1"; return 0; }
            stop_live_topology() { echo "stop"; }
            main
        '
    )"
    rm -rf "$tmpdir"

    if [[ "$output" != *"launch:$REPO_ROOT/tests/headless/scripts/minimal.startscript"* ]]; then
        echo "test_itertesting_campaign: split live setup did not launch the natural smoke topology" >&2
        exit 1
    fi
    if [[ "$output" != *$'smoke\nstop\nlaunch:'"$REPO_ROOT"$'/tests/headless/scripts/cheats.startscript'* ]]; then
        echo "test_itertesting_campaign: split live setup did not relaunch on the cheat startscript after smoke" >&2
        exit 1
    fi
    if [[ "$output" != *$'\nmain:1\nstop'* ]]; then
        echo "test_itertesting_campaign: split live setup did not execute the seeded coverage run" >&2
        exit 1
    fi
}

assert_split_live_setup_forces_seeded_campaign_flags() {
    local tmpdir
    local output
    tmpdir="$(mktemp -d)"
    output="$(
        WRAPPER="$WRAPPER" \
        HIGHBAR_ITERTESTING_REPORTS_DIR="$tmpdir/reports" \
        HIGHBAR_RUN_DIR="$tmpdir/run" \
        HIGHBAR_WRITE_DIR="$tmpdir/write" \
        bash -lc '
            set -euo pipefail
            source "$WRAPPER"
            prepare_attempt_dir 1
            COORD_ENDPOINT="unix:/tmp/highbar-test.sock"
            ACTIVE_RUN_DIR="$HIGHBAR_RUN_DIR/attempt-1"
            latest_stop_decision_path() { return 0; }
            latest_run_manifest_path() { return 0; }
            emit_contract_health_notice() { return 1; }
            emit_fixture_provisioning_notice() { return 1; }
            should_retry_live_session() { return 1; }
            uv() { printf "%s\n" "$*"; }
            run_live_campaign 1
        '
    )"
    rm -rf "$tmpdir"

    if [[ "$output" != *"--allow-cheat-escalation --no-natural-first"* ]]; then
        echo "test_itertesting_campaign: split live setup did not force seeded campaign flags" >&2
        exit 1
    fi
}

assert_callback_proxy_endpoint_rebinds_per_attempt() {
    local expected_run_dir="${HIGHBAR_RUN_DIR:-/tmp/hb-run-itertesting}"
    mapfile -t rebound_endpoints < <(
        env WRAPPER_PATH="$WRAPPER" bash -lc '
            set -euo pipefail
            source "$WRAPPER_PATH"
            prepare_attempt_dir 1
            configure_live_attempt_env
            printf "%s\n" "$HIGHBAR_CALLBACK_PROXY_ENDPOINT"
            prepare_attempt_dir 2
            configure_live_attempt_env
            printf "%s\n" "$HIGHBAR_CALLBACK_PROXY_ENDPOINT"
        '
    )
    if [[ "${rebound_endpoints[0]:-}" != "unix:$expected_run_dir/attempt-1/highbar-1.sock" ]]; then
        echo "test_itertesting_campaign: attempt 1 callback proxy endpoint did not bind to its run dir" >&2
        exit 1
    fi
    if [[ "${rebound_endpoints[1]:-}" != "unix:$expected_run_dir/attempt-2/highbar-1.sock" ]]; then
        echo "test_itertesting_campaign: attempt 2 callback proxy endpoint reused stale state" >&2
        exit 1
    fi

    mapfile -t overridden_endpoints < <(
        env WRAPPER_PATH="$WRAPPER" HIGHBAR_CALLBACK_PROXY_ENDPOINT="unix:/tmp/highbar-custom.sock" bash -lc '
            set -euo pipefail
            source "$WRAPPER_PATH"
            prepare_attempt_dir 1
            configure_live_attempt_env
            printf "%s\n" "$HIGHBAR_CALLBACK_PROXY_ENDPOINT"
            prepare_attempt_dir 2
            configure_live_attempt_env
            printf "%s\n" "$HIGHBAR_CALLBACK_PROXY_ENDPOINT"
        '
    )
    if [[ "${overridden_endpoints[0]:-}" != "unix:/tmp/highbar-custom.sock" || "${overridden_endpoints[1]:-}" != "unix:/tmp/highbar-custom.sock" ]]; then
        echo "test_itertesting_campaign: explicit callback proxy override was not preserved" >&2
        exit 1
    fi
}

assert_autoquit_config_is_temporarily_disabled() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' RETURN
    mkdir -p "$tmpdir/LuaUI/Config" "$tmpdir/engine/recoil_2025.06.19/LuaUI/Config" "$tmpdir/run/attempt-1"
    cat > "$tmpdir/LuaUI/Config/BYAR.lua" <<'EOF'
return {
  data = {
    Autoquit = 43,
  },
  order = {
    Autoquit = 82,
    Awards = 31,
  }
}
EOF
    cat > "$tmpdir/engine/recoil_2025.06.19/LuaUI/Config/BYAR.lua" <<'EOF'
return {
  data = {
    Autoquit = 12,
  },
  order = {
    Autoquit = 43,
    Awards = 31,
  }
}
EOF
    env WRAPPER_PATH="$WRAPPER" TEST_WRITE_DIR="$tmpdir" TEST_ACTIVE_RUN_DIR="$tmpdir/run/attempt-1" bash -lc '
        set -euo pipefail
        source "$WRAPPER_PATH"
        WRITE_DIR="$TEST_WRITE_DIR"
        ACTIVE_RUN_DIR="$TEST_ACTIVE_RUN_DIR"
        disable_autoquit_for_attempt
        python3 - "$WRITE_DIR/LuaUI/Config/BYAR.lua" "$WRITE_DIR/engine/recoil_2025.06.19/LuaUI/Config/BYAR.lua" <<'"'"'PY'"'"'
from pathlib import Path
import sys
user_text = Path(sys.argv[1]).read_text(encoding="utf-8")
engine_text = Path(sys.argv[2]).read_text(encoding="utf-8")
assert "order = {" in user_text
assert "order = {" in engine_text
assert "Autoquit = 0," in user_text
assert "Autoquit = 0," in engine_text
assert "Awards = 31," in user_text
assert "Awards = 31," in engine_text
assert "data = {\n    Autoquit = 43," in user_text
assert "data = {\n    Autoquit = 12," in engine_text
PY
        restore_autoquit_config
        python3 - "$WRITE_DIR/LuaUI/Config/BYAR.lua" "$WRITE_DIR/engine/recoil_2025.06.19/LuaUI/Config/BYAR.lua" <<'"'"'PY'"'"'
from pathlib import Path
import sys
user_text = Path(sys.argv[1]).read_text(encoding="utf-8")
engine_text = Path(sys.argv[2]).read_text(encoding="utf-8")
assert "Autoquit = 82," in user_text
assert "Autoquit = 43," in engine_text
assert "Awards = 31," in user_text
assert "Awards = 31," in engine_text
assert "data = {\n    Autoquit = 43," in user_text
assert "data = {\n    Autoquit = 12," in engine_text
PY
    '
    trap - RETURN
    rm -rf "$tmpdir"
}

assert_semantic_gate_bundle() {
    local reports_dir="$1"
    uv run --project "$REPO_ROOT/clients/python" python - "$reports_dir" <<'PY'
import sys
from pathlib import Path

from highbar_client.behavioral_coverage.itertesting_runner import build_run, write_run_bundle
from highbar_client.behavioral_coverage.registry import REGISTRY

reports_dir = Path(sys.argv[1]) / "semantic-gates"
reports_dir.mkdir(parents=True, exist_ok=True)
run = build_run(
    campaign_id="semantic-campaign",
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
    ],
)
write_run_bundle(run, reports_dir)
PY

    local manifest
    manifest="$(find "$reports_dir/semantic-gates" -path '*/manifest.json' | sort | tail -n1)"
    python3 - "$manifest" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

semantic_gates = {item["command_id"]: item for item in payload.get("semantic_gates", [])}
assert semantic_gates["cmd-set-wanted-max-speed"]["gate_kind"] == "mod-option"
assert semantic_gates["cmd-dgun"]["gate_kind"] == "unit-shape"
assert semantic_gates["cmd-attack"]["gate_kind"] == "lua-rewrite"
assert payload.get("fully_interpreted") is True
assert payload.get("decision_trace")
summary = payload.get("summary") or {}
assert not summary.get("transport_interrupted")
decision = payload.get("contract_health_decision") or {}
assert decision.get("decision_status") == "ready_for_itertesting"
PY
}

assert_fixture_bundle_shape() {
    local reports_dir="$1"
    local manifest
    manifest="$(latest_manifest "$reports_dir")"
    python3 - "$manifest" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

fixture = payload.get("fixture_provisioning") or {}
transport = payload.get("transport_provisioning") or {}
class_statuses = fixture.get("class_statuses") or []
assert class_statuses, "fixture class statuses missing from manifest"
status_by_class = {item["fixture_class"]: item["status"] for item in class_statuses}
assert status_by_class["transport_unit"] in {"missing", "provisioned", "refreshed", "unusable"}
assert "affected_command_ids" in fixture
assert transport.get("status") in {"missing", "preexisting", "provisioned", "refreshed", "replaced", "fallback_provisioned", "unusable"}
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
assert_fixture_bundle_shape "$QUICK_DIR"
assert_fixture_bundle_shape "$STANDARD_DIR"
assert_fixture_bundle_shape "$DEEP_DIR"
assert_wrapper_semantic_inventory "$QUICK_DIR"
assert_split_live_setup_sequences_smoke_then_seeded
assert_split_live_setup_forces_seeded_campaign_flags
assert_callback_proxy_endpoint_rebinds_per_attempt
assert_autoquit_config_is_temporarily_disabled
assert_semantic_gate_bundle "$QUICK_DIR"

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
