#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

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
# The maintainer-facing live path is documented as a default single run.
# Keep profile-driven defaults for synthetic campaign validation, but
# clamp the live wrapper to one run unless the maintainer explicitly
# requests follow-up retries.
if [[ "$SKIP_LIVE" != "true" && -z "$MAX_RUNS" ]]; then
    MAX_RUNS="0"
fi
ACTIVE_RUN_DIR=""
COORD_SOCK=""
COORD_LOG=""
ENGINE_LOG=""
ENGINE_PID_FILE=""
COORD_PID=""

mkdir -p "$RUN_DIR"

stop_live_topology() {
    if [[ -f "$ENGINE_PID_FILE" ]]; then
        kill -TERM "$(cat "$ENGINE_PID_FILE")" 2>/dev/null || true
    fi
    if [[ -n "$COORD_PID" ]]; then
        kill -TERM "$COORD_PID" 2>/dev/null || true
    fi
    sleep 1
}

prepare_attempt_dir() {
    local attempt="$1"
    ACTIVE_RUN_DIR="$RUN_DIR/attempt-$attempt"
    rm -rf "$ACTIVE_RUN_DIR"
    mkdir -p "$ACTIVE_RUN_DIR"
    COORD_SOCK="$ACTIVE_RUN_DIR/hb-coord.sock"
    COORD_LOG="$ACTIVE_RUN_DIR/coord.log"
    ENGINE_LOG="$ACTIVE_RUN_DIR/highbar-launch.log"
    ENGINE_PID_FILE="$ACTIVE_RUN_DIR/highbar-launch.pid"
    COORD_PID=""
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
    rm -f "$COORD_SOCK"
    python3 "$EXAMPLES_DIR/coordinator.py" \
        --endpoint "unix:$COORD_SOCK" --id bcov > "$COORD_LOG" 2>&1 &
    COORD_PID=$!
    for _ in $(seq 1 20); do
        [[ -S "$COORD_SOCK" ]] && break
        sleep 0.2
    done
    if [[ ! -S "$COORD_SOCK" ]]; then
        echo "itertesting: coordinator failed to bind — skip" >&2
        return 77
    fi

    LAUNCH_OUT=$("$HEADLESS_DIR/_launch.sh" \
        --start-script "$START_SCRIPT" \
        --coordinator "unix:$COORD_SOCK" \
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
        --endpoint "unix:$COORD_SOCK"
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
    exit $rc
fi

attempt=1
total_attempts=$((LIVE_RETRIES + 1))
while [[ $attempt -le $total_attempts ]]; do
    prepare_attempt_dir "$attempt"
    launch_live_topology
    launch_rc=$?
    if [[ $launch_rc -ne 0 ]]; then
        exit $launch_rc
    fi

    run_live_campaign "$attempt"
    campaign_rc=$?
    if [[ $campaign_rc -eq 86 && $attempt -lt $total_attempts ]]; then
        echo "itertesting: retrying live run with a clean coordinator/engine session" >&2
        stop_live_topology
        attempt=$((attempt + 1))
        continue
    fi
    exit $campaign_rc
done
