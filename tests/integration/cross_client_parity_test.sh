#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

"$repo_root/.venv/bin/python" -m pytest \
  "$repo_root/clients/python/tests/test_command_diagnostics.py" \
  "$repo_root/clients/python/tests/test_command_capabilities.py" \
  "$repo_root/clients/python/tests/test_protobuf_proxy_safety_conformance.py"

dotnet build "$repo_root/clients/fsharp/HighBar.Client.fsproj" >/dev/null
dotnet build "$repo_root/clients/fsharp/samples/AiClient/AiClient.fsproj" >/dev/null

echo "cross_client_parity_test: PASS python fixtures and F# generated client build agree"
