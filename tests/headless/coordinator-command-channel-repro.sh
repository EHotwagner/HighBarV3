#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
EXAMPLES_DIR="$REPO_ROOT/specs/002-live-headless-e2e/examples"

# shellcheck source=tests/headless/_coordinator.sh
source "$HEADLESS_DIR/_coordinator.sh"

if [[ ! -f "$EXAMPLES_DIR/coordinator.py" ]]; then
    echo "coordinator-command-channel-repro: coordinator.py missing — skip" >&2
    exit 77
fi
if [[ ! -f "$EXAMPLES_DIR/command_channel_repro.py" ]]; then
    echo "coordinator-command-channel-repro: command_channel_repro.py missing — skip" >&2
    exit 77
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "coordinator-command-channel-repro: python3 missing — skip" >&2
    exit 77
fi

RUN_DIR="${HIGHBAR_RUN_DIR:-/tmp/hb-run-coordinator-command-channel-repro}"
TRANSPORT="${HIGHBAR_COORDINATOR_FORCE_TRANSPORT:-auto}"
REPRO_BATCHES="${HIGHBAR_REPRO_BATCHES:-3}"
REPRO_DELAY_MS="${HIGHBAR_REPRO_DELAY_MS:-150}"
REPRO_POST_WAIT_MS="${HIGHBAR_REPRO_POST_WAIT_MS:-500}"
COORD_LOG="$RUN_DIR/coord.log"
CLIENT_LOG="$RUN_DIR/client.log"

mkdir -p "$RUN_DIR"
rm -f "$COORD_LOG" "$CLIENT_LOG"

cleanup() {
    if [[ -n "${HIGHBAR_COORDINATOR_PID:-}" ]]; then
        kill -TERM "$HIGHBAR_COORDINATOR_PID" 2>/dev/null || true
        wait "$HIGHBAR_COORDINATOR_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

if ! highbar_start_coordinator "$EXAMPLES_DIR" "$RUN_DIR" "repro" "$COORD_LOG"; then
    echo "coordinator-command-channel-repro: coordinator failed to start — fail" >&2
    cat "$COORD_LOG" >&2
    exit 1
fi

echo "coordinator-command-channel-repro: transport=$HIGHBAR_COORDINATOR_TRANSPORT endpoint=$HIGHBAR_COORDINATOR_ENDPOINT"

set +e
python3 "$EXAMPLES_DIR/command_channel_repro.py" \
    --endpoint "$HIGHBAR_COORDINATOR_ENDPOINT" \
    --batches "$REPRO_BATCHES" \
    --delay-ms "$REPRO_DELAY_MS" \
    --post-wait-ms "$REPRO_POST_WAIT_MS" >"$CLIENT_LOG" 2>&1
rc=$?
set -e

cat "$CLIENT_LOG"
echo "--- coordinator ---"
cat "$COORD_LOG"

if [[ $rc -eq 0 ]]; then
    echo "coordinator-command-channel-repro: PASS transport=$HIGHBAR_COORDINATOR_TRANSPORT"
    exit 0
fi

echo "coordinator-command-channel-repro: FAIL transport=$HIGHBAR_COORDINATOR_TRANSPORT rc=$rc" >&2
exit $rc
