#!/usr/bin/env bash
# T016 — gateway fault-state assertion helper.
#
# Sourced by every acceptance script that needs to distinguish a
# healthy gateway from a disabled-via-fault gateway. The contract is
# in specs/002-live-headless-e2e/contracts/gateway-fault.md §4.
#
# Usage (sourced):
#   source "$(dirname "$0")/_fault-assert.sh"
#   fault_status "$WRITE_DIR" || exit $?
#
# fault_status <write_dir> exits (NOT returns — the caller must use
# `fault_status ... || exit $?` to propagate) the following codes:
#   0  — gateway is healthy (status:healthy)
#   2  — gateway is disabled (status:disabled); the caller should
#        convert this into an explicit failure (exit 1) rather than a
#        skip, per FR-024.
#   77 — indeterminate (no highbar.health file); treat as "plugin
#        never ran" or "pre-session" and fall back to whatever prereq
#        check the caller normally does.
#   other nonzero — parse error.

fault_status() {
    local write_dir="${1:-}"
    if [[ -z "$write_dir" ]]; then
        echo "fault_status: missing write_dir argument" >&2
        return 3
    fi

    local health_file="$write_dir/highbar.health"
    if [[ ! -f "$health_file" ]]; then
        return 77  # indeterminate
    fi

    local content
    content="$(cat "$health_file" 2>/dev/null)" || return 4

    # Single-line JSON per contracts/gateway-fault.md §2. Substring match
    # on "status":"healthy" / "status":"disabled" — stable since the
    # writer emits a stable field order (status first).
    if [[ "$content" == *'"status":"healthy"'* ]]; then
        return 0
    elif [[ "$content" == *'"status":"disabled"'* ]]; then
        # Extract subsystem/reason for the caller's log if needed.
        local subsystem reason
        subsystem="$(echo "$content" | sed -n 's/.*"subsystem":"\([^"]*\)".*/\1/p')"
        reason="$(echo "$content" | sed -n 's/.*"reason":"\([^"]*\)".*/\1/p')"
        echo "fault_status: gateway DISABLED — subsystem=$subsystem reason=$reason" >&2
        return 2
    else
        echo "fault_status: unrecognized health content: $content" >&2
        return 5
    fi
}

# Convenience: acceptance scripts call this to upgrade a disabled-state
# finding into a loud test failure (never a skip). Takes the write_dir
# and the script's current exit code; returns the adjusted code.
#
#   exit_code=$?
#   exit_code=$(fault_guard "$WRITE_DIR" "$exit_code")
#   exit "$exit_code"
fault_guard() {
    local write_dir="${1:-}"
    local cur_exit="${2:-0}"
    fault_status "$write_dir"
    local fs=$?
    case "$fs" in
        0)  echo "$cur_exit" ;;           # healthy — preserve caller's exit
        2)  echo "1" ;;                   # disabled — upgrade to failure (FR-024)
        77) echo "$cur_exit" ;;           # indeterminate — preserve caller's exit
        *)  echo "1" ;;                   # parse error — fail loudly
    esac
}
