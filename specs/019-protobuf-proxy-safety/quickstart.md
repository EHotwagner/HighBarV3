# Quickstart: Non-Python Client Protobuf And Proxy Safety

## Prerequisites

- `buf`, `protoc`, CMake, Ninja, vcpkg-provided gRPC/Protobuf, Python 3.11+, and .NET 8 available in the maintainer environment.
- BAR headless fixtures available for the existing `tests/headless/*.sh` scripts.
- Work from the repository root on branch `019-protobuf-proxy-safety`.

## Generate Proto Stubs

```bash
buf lint proto
cd proto && buf generate
```

Confirm generated outputs update all required surfaces:

```bash
git status --short proto src/circuit/grpc clients/python/highbar_client/highbar clients/fsharp
```

## Build And Run Focused Native Tests

```bash
cmake --build /home/developer/recoil-engine/build --target \
  command_validation_test command_queue_test command_validation_perf_test \
  command_capabilities_test order_state_tracker_test admin_control_test \
  command_diagnostics_test integration_admin_control_test BARb
ctest --test-dir /home/developer/recoil-engine/build --output-on-failure \
  -R 'command_validation|command_queue|command_capabilities|order_state|admin_control|command_diagnostics'
```

Expected coverage:

- Structured issue codes and retry hints for malformed batches.
- Atomic batch rejection on queue capacity.
- Validator overhead remains within the existing p99 budget.
- Capability discovery, order-state conflict checks, admin leases, and
  command diagnostic integration slices pass.

## Run Client-Side Checks

```bash
.venv/bin/python -m pytest clients/python/tests
```

```bash
dotnet build clients/fsharp/HighBar.Client.fsproj
dotnet build clients/fsharp/samples/AiClient/AiClient.fsproj
```

Expected coverage:

- Python helpers continue to submit existing commands in compatibility/warning mode.
- F# generated stubs compile against the additive proto changes.
- Samples can read the preserved aggregate `CommandAck` counters and optionally inspect new per-batch results.
- Current local result on 2026-04-24: 233 Python tests passed, 4 live-gateway tests skipped without a running match.

## Run Contract And Headless Evidence

```bash
tests/headless/test_command_contract_hardening.sh
tests/headless/protobuf-proxy-safety.sh --mode warning-only
tests/headless/protobuf-proxy-safety.sh --mode strict
tests/integration/cross_client_parity_test.sh
```

Expected evidence:

- Warning-only mode records would-reject diagnostics without changing simulation behavior.
- Strict mode rejects missing correlation/state-basis, stale commands, invalid targets, invalid options, admin commands on the AI path, and accidental immediate replacement.
- Dispatch-time failures appear in state deltas within one update cycle.
- Current generated reports:
  `build/reports/protobuf-proxy-safety/warning-only.md` and
  `build/reports/protobuf-proxy-safety/strict.md`.

## Validate Admin Control Separation

Use generated clients to call:

- `HighBarAdmin.GetAdminCapabilities`
- `HighBarAdmin.ValidateAdminAction`
- `HighBarAdmin.ExecuteAdminAction`

Expected behavior:

- Normal AI credentials are denied privileged pause, speed, cheat, and lifecycle actions.
- Authorized run-scoped admin/test-harness credentials can dry-run and execute only actions enabled by config and run mode.
- Conflicting pause/speed control is rejected while another controller owns a live lease.
- Every accepted or rejected admin action and lease expiry emits an audit event.

## Rollout Gate

Before enabling strict mode by default:

1. Run the shared conformance fixture suite with Python and at least one generated non-Python client.
2. Confirm equivalent statuses, issue codes, retry hints, and field paths.
3. Run at least three prepared live/headless warning-only runs.
4. Compare would-reject counts and confirm maintainers understand every remaining warning.

Current warning-only report has `would_reject_count: 0`; there are no
compatibility exceptions recorded. The latency benches
`tests/bench/latency-uds.sh` and `tests/bench/latency-tcp.sh` skip with
exit 77 when no live stream produces samples; rerun them during a
headless/live gateway session before enabling strict mode by default.
