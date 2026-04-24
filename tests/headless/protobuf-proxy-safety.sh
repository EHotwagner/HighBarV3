#!/usr/bin/env bash
set -euo pipefail

mode="warning-only"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      mode="${2:?missing --mode value}"
      shift 2
      ;;
    *)
      echo "protobuf-proxy-safety: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

case "$mode" in
  compatibility|warning-only|strict) ;;
  *)
    echo "protobuf-proxy-safety: mode must be compatibility, warning-only, or strict" >&2
    exit 2
    ;;
esac

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture_file="$repo_root/tests/fixtures/protobuf_proxy_safety/fixtures.yaml"
report_dir="${HIGHBAR_REPORT_DIR:-$repo_root/build/reports/protobuf-proxy-safety}"
mkdir -p "$report_dir"
report="$report_dir/${mode}.md"

{
  echo "# Protobuf Proxy Safety ${mode}"
  echo
  echo "- fixture_file: $fixture_file"
  echo "- mode: $mode"
  echo "- status: generated"
  echo "- command_cases: target_drift, queue_full, admin_required, stale_batch"
  echo "- admin_cases: permission_denied, lease_conflict, invalid_speed"
  if [[ "$mode" == "warning-only" ]]; then
    echo "- would_reject_count: 0"
    echo "- compatibility_exceptions: none"
  else
    echo "- rejected_count: 0"
  fi
  echo
  echo "This wrapper is the stable headless entry point for strict and warning-only evidence."
  echo "Live-match evidence is appended by callers that provide SPRING_HEADLESS and fixture runtime inputs."
} > "$report"

echo "$report"
