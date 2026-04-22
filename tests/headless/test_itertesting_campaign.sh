#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPORTS_DIR="$(mktemp -d)"
trap 'rm -rf "$REPORTS_DIR"' EXIT

if [[ ! -x "$REPO_ROOT/tests/headless/itertesting.sh" ]]; then
    echo "test_itertesting_campaign: wrapper missing — fail" >&2
    exit 1
fi

HIGHBAR_ITERTESTING_REPORTS_DIR="$REPORTS_DIR" \
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=1 \
"$REPO_ROOT/tests/headless/itertesting.sh"

manifest_count="$(find "$REPORTS_DIR" -path '*/manifest.json' | wc -l | tr -d ' ')"
report_count="$(find "$REPORTS_DIR" -path '*/run-report.md' | wc -l | tr -d ' ')"

if [[ "$manifest_count" -lt 2 || "$report_count" -lt 2 ]]; then
    echo "test_itertesting_campaign: expected chained run bundles" >&2
    exit 1
fi

echo "PASS: itertesting campaign generated $manifest_count manifests and $report_count reports"
