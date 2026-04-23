#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_coordinator.sh
source "$HEADLESS_DIR/_coordinator.sh"
# shellcheck source=tests/headless/_fault-assert.sh
source "$HEADLESS_DIR/_fault-assert.sh"

if [[ ! -x "$HEADLESS_DIR/_launch.sh" ]]; then
    echo "itertesting: _launch.sh missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/coordinator.py" ]]; then
    echo "itertesting: coordinator.py missing — skip" >&2
    exit 77
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "itertesting: uv missing — skip" >&2
    exit 77
fi

RUN_DIR="${HIGHBAR_RUN_DIR:-/tmp/hb-run-itertesting}"
START_SCRIPT="${HIGHBAR_STARTSCRIPT:-$HEADLESS_DIR/scripts/minimal.startscript}"
CHEAT_STARTSCRIPT="${HIGHBAR_ITERTESTING_CHEAT_STARTSCRIPT:-$HEADLESS_DIR/scripts/cheats.startscript}"
WRITE_DIR="${HIGHBAR_WRITE_DIR:-$HOME/.local/state/Beyond All Reason}"
REPORTS_DIR="${HIGHBAR_ITERTESTING_REPORTS_DIR:-$REPO_ROOT/reports/itertesting}"
RETRY_INTENSITY="${HIGHBAR_ITERTESTING_RETRY_INTENSITY:-standard}"
RUNTIME_TARGET_MINUTES="${HIGHBAR_ITERTESTING_RUNTIME_TARGET_MINUTES:-15}"
SKIP_LIVE="${HIGHBAR_ITERTESTING_SKIP_LIVE:-false}"
LIVE_RETRIES="${HIGHBAR_ITERTESTING_LIVE_RETRIES:-1}"
THRESHOLD="${HIGHBAR_BEHAVIORAL_THRESHOLD:-0.50}"
GAMESEED="${HIGHBAR_GAMESEED:-0x42424242}"
MAX_RUNS="${HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS:-}"
BOOTSTRAP_WAIT_SECONDS="${HIGHBAR_ITERTESTING_BOOTSTRAP_WAIT_SECONDS:-12}"
ENABLE_BUILTIN="${HIGHBAR_ITERTESTING_ENABLE_BUILTIN:-false}"
EXPLICIT_CALLBACK_PROXY_ENDPOINT="${HIGHBAR_CALLBACK_PROXY_ENDPOINT:-}"
# The maintainer-facing live path is documented as a default single run.
# Keep profile-driven defaults for synthetic campaign validation, but
# clamp the live wrapper to one run unless the maintainer explicitly
# requests follow-up retries.
if [[ "$SKIP_LIVE" != "true" && -z "$MAX_RUNS" ]]; then
    MAX_RUNS="0"
fi
ACTIVE_RUN_DIR=""
COORD_SOCK=""
COORD_ENDPOINT=""
COORD_LOG=""
ENGINE_LOG=""
ENGINE_PID_FILE=""
COORD_PID=""
BYAR_USER_CONFIG_PATH=""
BYAR_USER_CONFIG_BACKUP=""
BYAR_ENGINE_CONFIG_PATH=""
BYAR_ENGINE_CONFIG_BACKUP=""

mkdir -p "$RUN_DIR"

patch_autoquit_config() {
    local config_path="$1"
    local backup_path="$2"
    if [[ ! -f "$config_path" ]]; then
        return 1
    fi
    cp "$config_path" "$backup_path"
    python3 - "$config_path" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
updated_lines: list[str] = []
inside_order = False
order_depth = 0
updated = False

for line in lines:
    if not inside_order and re.match(r'^\s*order\s*=\s*{', line):
        inside_order = True
        order_depth = line.count("{") - line.count("}")
        updated_lines.append(line)
        continue

    if inside_order and not updated:
        replaced, count = re.subn(r'^(\s*Autoquit\s*=\s*)\d+(,\s*)$', r'\g<1>0\2', line)
        if count:
            line = replaced
            updated = True

    updated_lines.append(line)

    if inside_order:
        order_depth += line.count("{") - line.count("}")
        if order_depth <= 0:
            inside_order = False

if not updated:
    raise SystemExit(1)

path.write_text("".join(updated_lines), encoding="utf-8")
PY
    return $?
}

disable_autoquit_for_attempt() {
    local engine_release="${HIGHBAR_ENGINE_RELEASE:-recoil_2025.06.19}"
    BYAR_USER_CONFIG_PATH="$WRITE_DIR/LuaUI/Config/BYAR.lua"
    BYAR_USER_CONFIG_BACKUP="$ACTIVE_RUN_DIR/BYAR.user.pre-highbar"
    BYAR_ENGINE_CONFIG_PATH="$WRITE_DIR/engine/$engine_release/LuaUI/Config/BYAR.lua"
    BYAR_ENGINE_CONFIG_BACKUP="$ACTIVE_RUN_DIR/BYAR.engine.pre-highbar"

    if ! patch_autoquit_config "$BYAR_USER_CONFIG_PATH" "$BYAR_USER_CONFIG_BACKUP"; then
        BYAR_USER_CONFIG_PATH=""
        BYAR_USER_CONFIG_BACKUP=""
    fi
    if ! patch_autoquit_config "$BYAR_ENGINE_CONFIG_PATH" "$BYAR_ENGINE_CONFIG_BACKUP"; then
        BYAR_ENGINE_CONFIG_PATH=""
        BYAR_ENGINE_CONFIG_BACKUP=""
    fi
}

restore_autoquit_config() {
    if [[ -n "$BYAR_USER_CONFIG_PATH" && -n "$BYAR_USER_CONFIG_BACKUP" && -f "$BYAR_USER_CONFIG_BACKUP" ]]; then
        cp "$BYAR_USER_CONFIG_BACKUP" "$BYAR_USER_CONFIG_PATH"
    fi
    if [[ -n "$BYAR_ENGINE_CONFIG_PATH" && -n "$BYAR_ENGINE_CONFIG_BACKUP" && -f "$BYAR_ENGINE_CONFIG_BACKUP" ]]; then
        cp "$BYAR_ENGINE_CONFIG_BACKUP" "$BYAR_ENGINE_CONFIG_PATH"
    fi
    BYAR_USER_CONFIG_PATH=""
    BYAR_USER_CONFIG_BACKUP=""
    BYAR_ENGINE_CONFIG_PATH=""
    BYAR_ENGINE_CONFIG_BACKUP=""
}

stop_live_topology() {
    if [[ -f "$ENGINE_PID_FILE" ]]; then
        kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null || true
    fi
    if [[ -n "$COORD_PID" ]]; then
        kill -TERM "$COORD_PID" 2>/dev/null || true
    fi
    sleep 1
    restore_autoquit_config
}

prepare_attempt_dir() {
    local attempt="$1"
    ACTIVE_RUN_DIR="$RUN_DIR/attempt-$attempt"
    rm -rf "$ACTIVE_RUN_DIR"
    mkdir -p "$ACTIVE_RUN_DIR"
    COORD_SOCK="$ACTIVE_RUN_DIR/hb-coord.sock"
    COORD_ENDPOINT=""
    COORD_LOG="$ACTIVE_RUN_DIR/coord.log"
    ENGINE_LOG="$ACTIVE_RUN_DIR/highbar-launch.log"
    ENGINE_PID_FILE="$ACTIVE_RUN_DIR/highbar-launch.pid"
    COORD_PID=""
}

configure_live_attempt_env() {
    export HIGHBAR_WRITE_DIR="$WRITE_DIR"
    export HIGHBAR_ENGINE_RELEASE="recoil_2025.06.19"
    export HIGHBAR_COORDINATOR_OWNER_SKIRMISH_AI_ID="${HIGHBAR_COORDINATOR_OWNER_SKIRMISH_AI_ID:-1}"
    export HIGHBAR_TOKEN_PATH="${HIGHBAR_TOKEN_PATH:-/tmp/highbar.token}"
    if [[ -n "$EXPLICIT_CALLBACK_PROXY_ENDPOINT" ]]; then
        export HIGHBAR_CALLBACK_PROXY_ENDPOINT="$EXPLICIT_CALLBACK_PROXY_ENDPOINT"
    else
        export HIGHBAR_CALLBACK_PROXY_ENDPOINT="unix:$ACTIVE_RUN_DIR/highbar-1.sock"
    fi
}

wait_for_gateway_startup() {
    for _ in $(seq 1 30); do
        if grep -q '\[hb-gateway\] startup' "$ENGINE_LOG" 2>/dev/null; then
            return 0
        fi
        sleep 1
    done
    return 1
}

latest_stop_decision_path() {
    find "$REPORTS_DIR" -maxdepth 2 -name 'campaign-stop-decision.json' -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr \
        | head -n 1 \
        | cut -d' ' -f2-
}

latest_run_manifest_path() {
    find "$REPORTS_DIR" -maxdepth 2 -name 'manifest.json' -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr \
        | head -n 1 \
        | cut -d' ' -f2-
}

emit_contract_health_notice() {
    local manifest_path="$1"
    if [[ -z "$manifest_path" || ! -f "$manifest_path" ]]; then
        return 1
    fi
    python3 - "$manifest_path" <<'PY'
import json
import os
import sys

manifest_path = sys.argv[1]
with open(manifest_path, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

decision = manifest.get("contract_health_decision") or {}
status = decision.get("decision_status", "ready_for_itertesting")
if status == "ready_for_itertesting":
    raise SystemExit(1)

report_path = os.path.join(os.path.dirname(manifest_path), "run-report.md")
print(f"itertesting: contract_health={status} report={report_path}")
for issue in manifest.get("contract_issues", ()):
    print(
        "itertesting: blocker="
        f"{issue.get('issue_id')} class={issue.get('issue_class')} "
        f"status={issue.get('status')}"
    )
for repro in manifest.get("deterministic_repros", ()):
    args = " ".join(repro.get("arguments", ()))
    command = " ".join(part for part in (repro.get("entrypoint", ""), args) if part)
    print(f"itertesting: repro[{repro.get('issue_id')}]={command}")
PY
}

emit_fixture_provisioning_notice() {
    local manifest_path="$1"
    if [[ -z "$manifest_path" || ! -f "$manifest_path" ]]; then
        return 1
    fi
    python3 - "$manifest_path" <<'PY'
import json
import re
import sys
from pathlib import Path

manifest_path = sys.argv[1]
with open(manifest_path, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

fixture = manifest.get("fixture_provisioning") or {}
transport = manifest.get("transport_provisioning") or {}
bootstrap = manifest.get("bootstrap_readiness") or {}
runtime_capability_profile = manifest.get("runtime_capability_profile") or {}
callback_diagnostics = manifest.get("callback_diagnostics") or []
prerequisite_resolution = manifest.get("prerequisite_resolution") or []
map_source_decisions = manifest.get("map_source_decisions") or []
interpretation_warnings = manifest.get("interpretation_warnings") or []
decision_trace = manifest.get("decision_trace") or []
class_statuses = fixture.get("class_statuses") or []
if not class_statuses:
    raise SystemExit(1)

affected = fixture.get("affected_command_ids") or []
print(
    "itertesting: fixture_statuses="
    + ",".join(
        f"{item.get('fixture_class')}:{item.get('status')}"
        for item in class_statuses
    )
)
print(
    "itertesting: fixture_affected_commands="
    + (",".join(affected) if affected else "none")
)
print(
    "itertesting: transport_status="
    + transport.get("status", "none")
)
print(
    "itertesting: transport_affected_commands="
    + (
        ",".join(transport.get("affected_command_ids", ()))
        if transport.get("affected_command_ids")
        else "none"
    )
)
print(
    "itertesting: bootstrap_readiness="
    + bootstrap.get("readiness_status", "none")
)
print(
    "itertesting: callback_diagnostics="
    + ",".join(
        f"{item.get('capture_stage')}:{item.get('availability_status')}"
        for item in callback_diagnostics
    )
    if callback_diagnostics
    else "itertesting: callback_diagnostics=none"
)
print(
    "itertesting: runtime_capability_profile="
    + (
        f"callbacks={','.join(str(item) for item in runtime_capability_profile.get('supported_callbacks', ())) or 'none'} "
        f"map={runtime_capability_profile.get('map_data_source_status', 'none')}"
    )
)
print(
    "itertesting: prerequisite_resolution="
    + ",".join(
        f"{item.get('prerequisite_name')}:{item.get('resolution_status')}"
        for item in prerequisite_resolution
    )
    if prerequisite_resolution
    else "itertesting: prerequisite_resolution=none"
)
print(
    "itertesting: map_source_decisions="
    + ",".join(
        f"{item.get('consumer')}:{item.get('selected_source')}"
        for item in map_source_decisions
    )
    if map_source_decisions
    else "itertesting: map_source_decisions=none"
)
print(
    "itertesting: fully_interpreted="
    + ("yes" if manifest.get("fully_interpreted", True) else "no")
)
print(
    "itertesting: interpretation_warnings="
    + (
        ",".join(
            f"{item.get('record_type')}:{item.get('severity')}"
            for item in interpretation_warnings
        )
        if interpretation_warnings
        else "none"
    )
)
print(
    "itertesting: decision_trace="
    + (
        ",".join(
            f"{item.get('concern')}:{item.get('source_layer')}"
            for item in decision_trace[:8]
        )
        if decision_trace
        else "none"
    )
)
report_path = Path(manifest_path).with_name("run-report.md")
semantic_inventory = []
if report_path.exists():
    in_section = False
    for line in report_path.read_text(encoding="utf-8").splitlines():
        if line == "## Command Semantic Inventory":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = re.match(r"- `(\d+)` `([^`]+)` .*`([^`]+)`", line)
        if match:
            semantic_inventory.append(
                f"{match.group(1)}:{match.group(2)}@{match.group(3)}"
            )
print(
    "itertesting: semantic_inventory="
    + (",".join(semantic_inventory) if semantic_inventory else "none")
)
semantic_gates = [
    item.get("command_id")
    + ":"
    + item.get("gate_kind", "")
    for item in manifest.get("semantic_gates", ())
]
print(
    "itertesting: semantic_gates="
    + (",".join(semantic_gates) if semantic_gates else "none")
)
PY
}

should_retry_live_session() {
    local manifest_path="$1"
    local decision_path="$2"
    local command_output="$3"
    local channel_dropped=1
    if [[ -f "$COORD_LOG" ]] && grep -q '\[cmd-ch\].*disconnected' "$COORD_LOG"; then
        channel_dropped=0
    fi

    if [[ -n "$manifest_path" && -f "$manifest_path" ]]; then
        python3 - "$manifest_path" "$decision_path" "$channel_dropped" <<'PY'
import json
import sys
manifest_path = sys.argv[1]
decision_path = sys.argv[2]
channel_dropped = sys.argv[3] == "0"
with open(manifest_path, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)
decision = {}
if decision_path and decision_path != "None":
    try:
        with open(decision_path, "r", encoding="utf-8") as handle:
            decision = json.load(handle)
    except FileNotFoundError:
        decision = {}
channel = manifest.get("channel_health") or {}
summary = manifest.get("summary") or {}
should_retry = (
    channel_dropped
    and channel.get("status") in {"degraded", "recovered", "interrupted"}
    and (
        decision.get("stop_reason") in {"stalled", "interrupted"}
        or summary.get("transport_interrupted")
    )
    and summary.get("direct_verified_total", 0) == 0
)
raise SystemExit(0 if should_retry else 1)
PY
        return $?
    fi

    if [[ $channel_dropped -eq 0 ]] && printf '%s\n' "$command_output" | grep -q 'plugin command channel is not connected'; then
        return 0
    fi

    return 1
}

launch_live_topology() {
    configure_live_attempt_env
    disable_autoquit_for_attempt
    if ! highbar_start_coordinator "$EXAMPLES_DIR" "$ACTIVE_RUN_DIR" "bcov" "$COORD_LOG"; then
        echo "itertesting: coordinator failed to bind on unix or tcp — skip" >&2
        cat "$COORD_LOG" >&2
        return 77
    fi
    COORD_PID="$HIGHBAR_COORDINATOR_PID"
    COORD_ENDPOINT="$HIGHBAR_COORDINATOR_ENDPOINT"

    LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
        --start-script "$START_SCRIPT" \
        --coordinator "$COORD_ENDPOINT" \
        --enable-builtin "$ENABLE_BUILTIN" \
        --runtime-dir "$ACTIVE_RUN_DIR" 2>&1)
    LAUNCH_RC=$?
    if [[ $LAUNCH_RC -eq 77 ]]; then
        echo "itertesting: _launch.sh prereq missing — skip" >&2
        return 77
    fi
    if [[ $LAUNCH_RC -ne 0 ]]; then
        echo "itertesting: _launch.sh failed — fail" >&2
        return 1
    fi

    if ! wait_for_gateway_startup; then
        echo "itertesting: gateway startup not seen — fail" >&2
        return 1
    fi

    EFFECTIVE_WRITEDIR="$WRITE_DIR/engine/recoil_2025.06.19"
    fault_status "$EFFECTIVE_WRITEDIR"
    fs=$?
    if [[ $fs -eq 2 ]]; then
        echo "itertesting: gateway Disabled at start — skip" >&2
        return 77
    fi

    sleep "$BOOTSTRAP_WAIT_SECONDS"
    return 0
}

run_live_campaign() {
    local attempt="$1"
    local out_file="$ACTIVE_RUN_DIR/itertesting.out"
    local before_stop=""
    local after_stop=""
    local before_manifest=""
    local after_manifest=""
    local command_output=""
    local rc=0

    before_stop="$(latest_stop_decision_path)"
    before_manifest="$(latest_run_manifest_path)"
    ARGS=(
        itertesting
        --endpoint "$COORD_ENDPOINT"
        --startscript "$START_SCRIPT"
        --reports-dir "$REPORTS_DIR"
        --retry-intensity "$RETRY_INTENSITY"
        --runtime-target-minutes "$RUNTIME_TARGET_MINUTES"
        --threshold "$THRESHOLD"
        --gameseed "$GAMESEED"
        --cheat-startscript "$CHEAT_STARTSCRIPT"
    )
    if [[ -n "$MAX_RUNS" ]]; then
        ARGS+=(--max-improvement-runs "$MAX_RUNS")
    fi
    if [[ "${HIGHBAR_ITERTESTING_ALLOW_CHEAT_ESCALATION:-false}" == "true" ]]; then
        ARGS+=(--allow-cheat-escalation)
    fi

    echo "itertesting: invoking live campaign (attempt $attempt): ${ARGS[*]}"
    uv run --project "$REPO_ROOT/clients/python" python -m highbar_client.behavioral_coverage "${ARGS[@]}" >"$out_file" 2>&1
    rc=$?
    command_output="$(cat "$out_file")"
    printf '%s\n' "$command_output"

    after_stop="$(latest_stop_decision_path)"
    after_manifest="$(latest_run_manifest_path)"
    emit_contract_health_notice "$after_manifest" || true
    emit_fixture_provisioning_notice "$after_manifest" || true
    if should_retry_live_session "$after_manifest" "$after_stop" "$command_output"; then
        if [[ "$after_stop" != "$before_stop" && -n "$after_stop" ]]; then
            echo "itertesting: live session degraded; latest stop decision=$(basename "$(dirname "$after_stop")")/$(basename "$after_stop")" >&2
        elif [[ "$after_manifest" != "$before_manifest" && -n "$after_manifest" ]]; then
            echo "itertesting: live session degraded; latest manifest=$(basename "$(dirname "$after_manifest")")/$(basename "$after_manifest")" >&2
        else
            echo "itertesting: live session degraded before a new stop decision artifact was written" >&2
        fi
        return 86
    fi

    return $rc
}

cleanup() {
    stop_live_topology
}

main() {
    trap cleanup EXIT

    if [[ "$SKIP_LIVE" == "true" ]]; then
        ARGS=(
            itertesting
            --reports-dir "$REPORTS_DIR"
            --retry-intensity "$RETRY_INTENSITY"
            --runtime-target-minutes "$RUNTIME_TARGET_MINUTES"
            --threshold "$THRESHOLD"
            --gameseed "$GAMESEED"
            --cheat-startscript "$CHEAT_STARTSCRIPT"
            --skip-live
        )
        if [[ -n "$MAX_RUNS" ]]; then
            ARGS+=(--max-improvement-runs "$MAX_RUNS")
        fi

        if [[ "${HIGHBAR_ITERTESTING_ALLOW_CHEAT_ESCALATION:-false}" == "true" ]]; then
            ARGS+=(--allow-cheat-escalation)
        fi

        echo "itertesting: invoking synthetic campaign: ${ARGS[*]}"
        uv run --project "$REPO_ROOT/clients/python" python -m highbar_client.behavioral_coverage "${ARGS[@]}" "$@"
        rc=$?
        emit_contract_health_notice "$(latest_run_manifest_path)" || true
        emit_fixture_provisioning_notice "$(latest_run_manifest_path)" || true
        return $rc
    fi

    attempt=1
    total_attempts=$((LIVE_RETRIES + 1))
    while [[ $attempt -le $total_attempts ]]; do
        prepare_attempt_dir "$attempt"
        launch_live_topology
        launch_rc=$?
        if [[ $launch_rc -ne 0 ]]; then
            return $launch_rc
        fi

        run_live_campaign "$attempt"
        campaign_rc=$?
        if [[ $campaign_rc -eq 86 && $attempt -lt $total_attempts ]]; then
            echo "itertesting: retrying live run with a clean coordinator/engine session" >&2
            stop_live_topology
            attempt=$((attempt + 1))
            continue
        fi
        return $campaign_rc
    done
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
