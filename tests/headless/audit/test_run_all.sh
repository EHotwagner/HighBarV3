#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
output="$("${repo_root}/tests/headless/audit/run-all.sh")"

grep -q "PASS: live audit evidence refreshed" <<<"${output}"
grep -q "Manifest:" <<<"${output}"
