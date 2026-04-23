#!/usr/bin/env bash
# T018 — shared spring-headless launcher used by BUILD.md step 9 + the
# acceptance suite. Validates the engine binary's SHA matches the pin
# in data/config/spring-headless.pin, exports SPRING_DATADIR +
# XDG_RUNTIME_DIR, launches the engine, optionally plumbs the
# coordinator endpoint, and writes the engine PID to a file the caller
# can wait on or kill.
#
# Usage:
#   _launch.sh \
#       --start-script <path> \
#       --plugin-so    <path>           # optional, install the .so first
#       --engine       <path>           # default: ~/.local/state/.../spring-headless
#       --log          <path>           # default: $TMPDIR/highbar-launch.log
#       --pid-file     <path>           # default: $TMPDIR/highbar-launch.pid
#       --coordinator  <uri>            # optional, sets HIGHBAR_COORDINATOR
#       --writedir     <path>           # default: $HOME/.local/state/Beyond All Reason
#       --runtime-dir  <path>           # default: $TMPDIR/hb-run
#
# Exits 0 if the engine starts and writes a PID file; 77 if a
# prerequisite is missing (engine binary, pin file, mismatched SHA);
# 1 on any other failure.

set -euo pipefail

START_SCRIPT=""
PLUGIN_SO=""
ENGINE=""
LOG=""
PID_FILE=""
COORDINATOR=""
WRITEDIR="${HOME}/.local/state/Beyond All Reason"
RUNTIME_DIR=""
PHASE_MODE="1"
ENABLE_BUILTIN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --start-script) START_SCRIPT="$2"; shift 2 ;;
        --plugin-so)    PLUGIN_SO="$2";    shift 2 ;;
        --engine)       ENGINE="$2";       shift 2 ;;
        --log)          LOG="$2";          shift 2 ;;
        --pid-file)     PID_FILE="$2";     shift 2 ;;
        --coordinator)  COORDINATOR="$2";  shift 2 ;;
        --writedir)     WRITEDIR="$2";     shift 2 ;;
        --runtime-dir)  RUNTIME_DIR="$2";  shift 2 ;;
        --phase)        PHASE_MODE="$2";   shift 2 ;;
        --enable-builtin) ENABLE_BUILTIN="$2"; shift 2 ;;
        -h|--help)
            sed -n '/^# Usage:/,/^$/p' "$0" >&2
            exit 0
            ;;
        *) echo "_launch.sh: unknown arg: $1" >&2; exit 1 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
PIN_FILE="$REPO_ROOT/data/config/spring-headless.pin"
LUA_GADGET_SRC_DIR="$REPO_ROOT/tests/headless/LuaRules/Gadgets"

# --- prerequisite checks (exit 77 on missing) --------------------------------

if [[ ! -f "$PIN_FILE" ]]; then
    echo "_launch.sh: pin file missing at $PIN_FILE" >&2
    exit 77
fi

PIN_SHA="$(grep -E '^sha256[[:space:]]*=' "$PIN_FILE" | sed 's/.*"\([^"]*\)".*/\1/')"
PIN_RELEASE="$(grep -E '^release_id[[:space:]]*=' "$PIN_FILE" | sed 's/.*"\([^"]*\)".*/\1/')"

if [[ -z "$ENGINE" ]]; then
    ENGINE="$WRITEDIR/engine/$PIN_RELEASE/spring-headless"
fi
if [[ ! -x "$ENGINE" ]]; then
    echo "_launch.sh: engine binary not found at $ENGINE" >&2
    exit 77
fi

ACTUAL_SHA="$(sha256sum "$ENGINE" | cut -d' ' -f1)"
if [[ "$ACTUAL_SHA" != "$PIN_SHA" ]]; then
    echo "_launch.sh: engine SHA mismatch: pin=$PIN_SHA actual=$ACTUAL_SHA" >&2
    exit 77
fi

if [[ -z "$START_SCRIPT" ]]; then
    echo "_launch.sh: --start-script required" >&2
    exit 1
fi
if [[ ! -f "$START_SCRIPT" ]]; then
    echo "_launch.sh: start script missing at $START_SCRIPT" >&2
    exit 77
fi

# --- optional plugin install --------------------------------------------------

if [[ -n "$PLUGIN_SO" ]]; then
    if [[ ! -f "$PLUGIN_SO" ]]; then
        echo "_launch.sh: --plugin-so given but file missing: $PLUGIN_SO" >&2
        exit 1
    fi
    BARB_DIR="$WRITEDIR/engine/$PIN_RELEASE/AI/Skirmish/BARb/stable"
    if [[ ! -d "$BARB_DIR" ]]; then
        echo "_launch.sh: BAR's BARb AI dir missing at $BARB_DIR" >&2
        exit 77
    fi
    if [[ ! -f "$BARB_DIR/libSkirmishAI.so.upstream-backup" ]]; then
        cp "$BARB_DIR/libSkirmishAI.so" \
           "$BARB_DIR/libSkirmishAI.so.upstream-backup"
    fi
    cp "$PLUGIN_SO" "$BARB_DIR/libSkirmishAI.so"
fi

# --- environment + launch ----------------------------------------------------

if [[ -z "$RUNTIME_DIR" ]]; then
    RUNTIME_DIR="${TMPDIR:-/tmp}/hb-run"
fi
mkdir -p "$RUNTIME_DIR"

if [[ -z "$LOG" ]];      then LOG="$RUNTIME_DIR/highbar-launch.log"; fi
if [[ -z "$PID_FILE" ]]; then PID_FILE="$RUNTIME_DIR/highbar-launch.pid"; fi

export SPRING_DATADIR="$WRITEDIR"
export XDG_RUNTIME_DIR="$RUNTIME_DIR"
[[ -n "$COORDINATOR" ]] && export HIGHBAR_COORDINATOR="$COORDINATOR"
export HIGHBAR_AUDIT_PHASE="$PHASE_MODE"
if [[ -n "$ENABLE_BUILTIN" ]]; then
    export HIGHBAR_ENABLE_BUILTIN="$ENABLE_BUILTIN"
elif [[ "$PHASE_MODE" == "2" ]]; then
    export HIGHBAR_ENABLE_BUILTIN="false"
else
    export HIGHBAR_ENABLE_BUILTIN="true"
fi

# Clear stale state files from prior runs.
rm -f "$RUNTIME_DIR/highbar-0.sock" \
      "$WRITEDIR/highbar.token" \
      "$WRITEDIR/highbar.health" \
      "$WRITEDIR/engine/$PIN_RELEASE/highbar.token" \
      "$WRITEDIR/engine/$PIN_RELEASE/highbar.health"

if [[ -d "$LUA_GADGET_SRC_DIR" ]]; then
    mkdir -p "$WRITEDIR/LuaRules/Gadgets"
    cp "$LUA_GADGET_SRC_DIR"/*.lua "$WRITEDIR/LuaRules/Gadgets/"
fi

"$ENGINE" "$START_SCRIPT" > "$LOG" 2>&1 &
SPRING_PID=$!
echo "$SPRING_PID" > "$PID_FILE"
echo "_launch.sh: started spring pid=$SPRING_PID log=$LOG"
echo "$SPRING_PID"
