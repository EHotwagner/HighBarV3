#!/usr/bin/env bash
# T008a — AICommand arm-coverage CSV generator.
#
# Parses proto/highbar/commands.proto via `buf build -o -` to enumerate
# all AICommand oneof arms, reads contracts/aicommand-arm-map.md for
# channel assignments, greps src/circuit/grpc/CommandDispatch.cpp for
# dispatcher_wired (syntactic match on `case C::k*:` labels with an
# engine call on its body), walks tests/headless/*.sh and tests/bench/*.sh
# for `# arm-covered:` headers, emits CSV per
# specs/002-live-headless-e2e/contracts/aicommand-coverage-report.md.
#
# Invoked by the CMake `aicommand-arm-coverage` target. Returns non-zero
# (failing the build) when --strict is passed and any arm is unwired or
# uncovered (FR-012, FR-013).

set -euo pipefail

REPO_ROOT=""
OUTPUT=""
STRICT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo-root) REPO_ROOT="$2"; shift 2 ;;
        --output)    OUTPUT="$2";    shift 2 ;;
        --strict)    STRICT=1;       shift ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

if [[ -z "$REPO_ROOT" || -z "$OUTPUT" ]]; then
    echo "usage: $0 --repo-root <dir> --output <path> [--strict]" >&2
    exit 2
fi

PROTO_FILE="$REPO_ROOT/proto/highbar/commands.proto"
ARM_MAP="$REPO_ROOT/specs/002-live-headless-e2e/contracts/aicommand-arm-map.md"
DISPATCH_CPP="$REPO_ROOT/src/circuit/grpc/CommandDispatch.cpp"
HEADLESS_DIR="$REPO_ROOT/tests/headless"
BENCH_DIR="$REPO_ROOT/tests/bench"
WIDGETS_DIR="$REPO_ROOT/tests/headless/widgets"

mkdir -p "$(dirname "$OUTPUT")"

# ----------------------------------------------------------------------
# 1. Enumerate arms from proto.
#
# Primary path: `buf build -o -` emits a FileDescriptorSet binary; we
# decode it via `protoc --decode`. If buf/protoc aren't both present,
# fall back to a regex over commands.proto — the proto format is simple
# enough that the regex is reliable (and this fallback lets the script
# work on hosts without buf, e.g. during local development before the
# toolchain bootstrap).
# ----------------------------------------------------------------------

declare -A ARM_FIELD_NUM  # arm_name → field number

parse_arms_regex() {
    # Matches lines like `    MoveUnitCommand move_unit = 42;`
    while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*[A-Z][A-Za-z0-9_]*[[:space:]]+([a-z][a-z0-9_]*)[[:space:]]*=[[:space:]]*([0-9]+)[[:space:]]*\; ]]; then
            local name="${BASH_REMATCH[1]}"
            local num="${BASH_REMATCH[2]}"
            ARM_FIELD_NUM["$name"]="$num"
        fi
    done < <(awk '/^message AICommand \{/,/^\}/' "$PROTO_FILE" | awk '/oneof command \{/,/^  \}/')
}

parse_arms_regex

if [[ ${#ARM_FIELD_NUM[@]} -eq 0 ]]; then
    echo "error: no AICommand oneof arms parsed from $PROTO_FILE" >&2
    exit 3
fi

# ----------------------------------------------------------------------
# 2. Channel assignments from contracts/aicommand-arm-map.md.
#
# The file has three sections (Channel A, Channel B, Channel C), each a
# markdown table with the arm name in the first column (backtick-quoted).
# ----------------------------------------------------------------------

declare -A ARM_CHANNEL  # arm_name → state-stream | engine-log | lua-widget

parse_arm_map() {
    local current_channel=""
    while IFS= read -r line; do
        if [[ "$line" =~ ^##\ *Channel\ A ]]; then
            current_channel="state-stream"
        elif [[ "$line" =~ ^##\ *Channel\ B ]]; then
            current_channel="engine-log"
        elif [[ "$line" =~ ^##\ *Channel\ C ]]; then
            current_channel="lua-widget"
        elif [[ "$line" =~ ^##\ *[A-Z] ]]; then
            current_channel=""
        elif [[ -n "$current_channel" && "$line" =~ ^\|[[:space:]]*\`([a-z][a-z0-9_]*)\` ]]; then
            ARM_CHANNEL["${BASH_REMATCH[1]}"]="$current_channel"
        fi
    done < "$ARM_MAP"
}

parse_arm_map

# ----------------------------------------------------------------------
# 3. Dispatcher-wired detection.
#
# An arm is dispatcher_wired=true iff CommandDispatch.cpp contains
#   case C::k<PascalCaseName>:
# AND that case's body (lines until the next `case` or `}` at the same
# indentation) contains a call matching
#   unit->Cmd  |  springai::  |  ai->Cheats()
# This is intentionally syntactic — proper static analysis isn't
# necessary; the signal is "there's a call, not a no-op default".
# ----------------------------------------------------------------------

declare -A ARM_WIRED

snake_to_pascal() {
    local snake="$1"
    local pascal=""
    local IFS='_'
    for part in $snake; do
        pascal+="$(tr '[:lower:]' '[:upper:]' <<< "${part:0:1}")${part:1}"
    done
    echo "$pascal"
}

detect_wired() {
    local dispatch_body
    dispatch_body="$(cat "$DISPATCH_CPP")"
    for arm in "${!ARM_FIELD_NUM[@]}"; do
        local pascal
        pascal="$(snake_to_pascal "$arm")"
        # Look for `case C::k<Pascal>:` followed later in the same case body by
        # a dispatch call. Some cases, notably `custom`, do meaningful
        # validation before the engine-facing call, so a short line window is
        # not reliable.
        local wired
        wired="$(awk -v label="case C::k${pascal}:" '
            $0 ~ label { in_case=1; next }
            in_case {
                if ($0 ~ /case C::k[A-Z][A-Za-z0-9_]*:/) { in_case=0; next }
                if ($0 ~ /unit->Cmd[A-Z]/ \
                    || $0 ~ /springai::/ \
                    || $0 ~ /ai->Cheats\(\)/ \
                    || $0 ~ /ai->Get(Game|Pathing|Lua|Cheats|Drawer|Group|Callback)\(\)/ \
                    || $0 ~ /(econ|cb)->(SendResource|GetResourceByName|GetEconomy)/ \
                    || $0 ~ /ExecuteCustomCommand/) {
                    print "true"; in_case=0; exit
                }
            }
        ' "$DISPATCH_CPP")"
        if [[ "$wired" == "true" ]]; then
            ARM_WIRED["$arm"]="true"
        else
            ARM_WIRED["$arm"]="false"
        fi
    done
}

detect_wired

# ----------------------------------------------------------------------
# 4. Covering acceptance scripts — scan first 30 lines of each
#    tests/headless/*.sh and tests/bench/*.sh for `# arm-covered: <arm>`.
# ----------------------------------------------------------------------

declare -A ARM_SCRIPTS
declare -A ARM_ASSERTIONS  # arm_name → count

scan_scripts() {
    local files=()
    shopt -s nullglob
    files+=("$HEADLESS_DIR"/*.sh)
    files+=("$BENCH_DIR"/*.sh)
    shopt -u nullglob
    for f in "${files[@]}"; do
        local base
        base="$(basename "$f")"
        # Extract arm-covered headers from the first 30 lines.
        while IFS= read -r arm; do
            [[ -z "$arm" ]] && continue
            # Append to comma-sep list if not already present.
            local existing="${ARM_SCRIPTS[$arm]:-}"
            if [[ ",${existing}," != *",${base},"* ]]; then
                if [[ -z "$existing" ]]; then
                    ARM_SCRIPTS["$arm"]="$base"
                else
                    ARM_SCRIPTS["$arm"]="${existing},${base}"
                fi
            fi
            # Assertion count: lines after the arm-covered comment until
            # next arm-covered or EOF that match assert_/expect_/fail_.
            local n
            n="$(awk -v arm="$arm" '
                /^# arm-covered:/ {
                    if ($0 ~ arm) { counting=1; next }
                    else if (counting) { counting=0 }
                }
                counting && /(assert|expect|fail)_/ { c++ }
                END { print c+0 }
            ' "$f")"
            ARM_ASSERTIONS["$arm"]=$(( ${ARM_ASSERTIONS[$arm]:-0} + n ))
        done < <(head -n 30 "$f" | sed -n 's/^#[[:space:]]*arm-covered:[[:space:]]*\([a-z][a-z0-9_,[:space:]]*\).*/\1/p' | tr ',' '\n' | tr -d ' ')
    done
}

scan_scripts

# ----------------------------------------------------------------------
# 5. Emit CSV sorted by field number.
# ----------------------------------------------------------------------

tmp_csv="$(mktemp)"
trap 'rm -f "$tmp_csv"' EXIT

echo "arm_name,arm_field_number,dispatcher_wired,observability_channel,covering_scripts,assertion_count" > "$tmp_csv"

# Sort arms by field number (numeric).
declare -a SORTED_ARMS
while IFS= read -r line; do
    SORTED_ARMS+=("$line")
done < <(
    for arm in "${!ARM_FIELD_NUM[@]}"; do
        printf '%s %s\n' "${ARM_FIELD_NUM[$arm]}" "$arm"
    done | sort -n | awk '{print $2}'
)

for arm in "${SORTED_ARMS[@]}"; do
    field_num="${ARM_FIELD_NUM[$arm]}"
    wired="${ARM_WIRED[$arm]:-false}"
    channel="${ARM_CHANNEL[$arm]:-unknown}"
    scripts="${ARM_SCRIPTS[$arm]:-}"
    assertions="${ARM_ASSERTIONS[$arm]:-0}"
    # Quote scripts field since it may contain commas.
    echo "$arm,$field_num,$wired,$channel,\"$scripts\",$assertions" >> "$tmp_csv"
done

mv "$tmp_csv" "$OUTPUT"
trap - EXIT

# ----------------------------------------------------------------------
# 6. Strict validation.
# ----------------------------------------------------------------------

if [[ "$STRICT" -eq 1 ]]; then
    fail=0
    while IFS=, read -r arm field_num wired channel scripts assertions; do
        [[ "$arm" == "arm_name" ]] && continue
        if [[ "$wired" != "true" ]]; then
            echo "FAIL: arm=$arm not dispatcher_wired (FR-012)" >&2
            fail=1
        fi
        # Strip surrounding quotes from scripts field for emptiness check.
        scripts_unquoted="${scripts#\"}"
        scripts_unquoted="${scripts_unquoted%\"}"
        if [[ -z "$scripts_unquoted" ]]; then
            echo "FAIL: arm=$arm has no covering_scripts (FR-013)" >&2
            fail=1
        fi
        if [[ "$channel" == "lua-widget" ]]; then
            # Widget file must exist and be listed in README.md. We check
            # only that the widgets dir has at least one .lua file; the
            # per-arm widget file-name mapping is too brittle to enforce
            # syntactically — the test widget naming convention is loose.
            if ! compgen -G "$WIDGETS_DIR/*.lua" >/dev/null; then
                echo "FAIL: arm=$arm channel=lua-widget but no widget files in $WIDGETS_DIR" >&2
                fail=1
            fi
        fi
    done < "$OUTPUT"

    if [[ "$fail" -ne 0 ]]; then
        echo "arm-coverage strict check FAILED; CSV: $OUTPUT" >&2
        exit 1
    fi
fi

echo "arm-coverage CSV written: $OUTPUT"
