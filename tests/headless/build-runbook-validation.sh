#!/usr/bin/env bash
# T020 — BUILD.md literate-runbook validator.
#
# Per contracts/build-runbook.md:
#   * Parse BUILD.md for `^## N. ` numbered H2 steps.
#   * Each step has exactly one fenced bash block.
#   * The fence is preceded by an HTML comment of the form
#     `<!-- expect: <substring> -->`.
#   * Execute each step's block in a single shared bash subshell so
#     env vars and CWD persist across steps.
#   * Combined stdout+stderr must contain the expect substring.
#   * On the first miss, exit non-zero with step number + last 200
#     lines of output.
#
# Exit codes:
#   0  all steps passed
#   1  a step's block exited non-zero or its expect substring missed
#   2  parser error (BUILD.md malformed)
#   77 BUILD.md not found at expected location

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
BUILD_MD="$REPO_ROOT/BUILD.md"
[[ -f "$BUILD_MD" ]] || { echo "BUILD.md not found at $BUILD_MD" >&2; exit 77; }

WORKDIR="$(mktemp -d -t hb-runbook-XXXXXX)"
trap 'rm -rf "$WORKDIR"' EXIT

# ----------------------------------------------------------------------
# 1. Parse BUILD.md → per-step (expect, body) pairs.
# ----------------------------------------------------------------------

awk '
BEGIN { step=0; in_block=0; expect=""; }
# H2 step heading.
/^## [0-9]+\. / {
    step = $2; sub(/\./, "", step); next
}
# Expect comment (single-line, immediately above the bash fence).
/^<!-- expect: .* -->[ \t]*$/ {
    expect = $0
    sub(/^<!-- expect: /, "", expect)
    sub(/ -->[ \t]*$/, "", expect)
    next
}
# Fenced bash open.
/^```bash[ \t]*$/ {
    if (step == 0) next
    in_block = 1
    out = sprintf("'"$WORKDIR"'/step_%02d.sh", step)
    expectfile = sprintf("'"$WORKDIR"'/step_%02d.expect", step)
    print expect > expectfile
    close(expectfile)
    next
}
# Fenced close.
/^```[ \t]*$/ {
    if (in_block) {
        in_block = 0
        close(out)
        expect = ""
    }
    next
}
in_block { print > out }
' "$BUILD_MD"

# ----------------------------------------------------------------------
# 2. Enumerate steps.
# ----------------------------------------------------------------------

mapfile -t STEPS < <(ls "$WORKDIR"/step_*.sh 2>/dev/null | sort)
if [[ ${#STEPS[@]} -eq 0 ]]; then
    echo "no numbered steps found in BUILD.md" >&2
    exit 2
fi
if [[ ${#STEPS[@]} -gt 10 ]]; then
    echo "BUILD.md has more than 10 numbered steps (found ${#STEPS[@]})" >&2
    exit 2
fi

echo "build-runbook-validation: found ${#STEPS[@]} steps in $BUILD_MD"

# ----------------------------------------------------------------------
# 3. Run each step in a single shared bash session.
# ----------------------------------------------------------------------

# Use a coprocess so we can keep one shell alive across all steps.
# Each step's body is sourced; the shared shell preserves env + cwd.
# We also append a unique end-of-step marker to know when output ends.

SESSION_LOG="$WORKDIR/session.log"
: > "$SESSION_LOG"

# Start a single bash that we feed per-step blocks into.
coproc SHELL { bash --noprofile --norc; }
exec {SH_IN}>&"${SHELL[1]}"
exec {SH_OUT}<&"${SHELL[0]}"

PASSED=0
FAILED_STEP=""
for step_file in "${STEPS[@]}"; do
    step_n="$(basename "$step_file" .sh | sed 's/step_0*//')"
    expect="$(cat "$WORKDIR/step_$(printf '%02d' "$step_n").expect")"

    if [[ -z "$expect" ]]; then
        echo "step $step_n: no expect substring in BUILD.md" >&2
        FAILED_STEP="$step_n"
        break
    fi

    echo "----- STEP $step_n -----"
    marker="HIGHBAR-RUNBOOK-END-OF-STEP-${step_n}-$$"
    {
        echo "echo '----- STEP $step_n start -----' 1>&2"
        cat "$step_file"
        echo
        echo "echo '$marker'"
        echo "echo '$marker' 1>&2"
    } >&"$SH_IN"

    # Read until we see the marker on stdout. Buffer to log + scan
    # for the expect substring.
    step_log="$WORKDIR/step_$(printf '%02d' "$step_n").log"
    : > "$step_log"
    while IFS= read -r -u "$SH_OUT" line; do
        echo "$line" >> "$step_log"
        echo "$line" >> "$SESSION_LOG"
        # Mirror to user terminal so the run is observable.
        echo "$line"
        if [[ "$line" == "$marker" ]]; then break; fi
    done

    if grep -F -q -- "$expect" "$step_log"; then
        echo "----- STEP $step_n PASS (matched: $expect) -----"
        PASSED=$((PASSED + 1))
    else
        echo "----- STEP $step_n FAIL (expected substring not in output: $expect) -----" >&2
        echo "--- last 200 lines of step output:" >&2
        tail -200 "$step_log" >&2
        FAILED_STEP="$step_n"
        break
    fi
done

# Clean up the coprocess.
exec {SH_IN}>&-
exec {SH_OUT}<&-
wait "$SHELL_PID" 2>/dev/null

if [[ -n "$FAILED_STEP" ]]; then
    echo ""
    echo "build-runbook-validation: FAIL at step $FAILED_STEP "
    echo "  ($PASSED of ${#STEPS[@]} steps passed before failure)"
    exit 1
fi

echo ""
echo "build-runbook-validation: PASS (all ${#STEPS[@]} steps green)"
exit 0
