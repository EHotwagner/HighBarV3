#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
PYTHONPATH="${repo_root}/clients/python" python -m highbar_client.behavioral_coverage audit phase2
