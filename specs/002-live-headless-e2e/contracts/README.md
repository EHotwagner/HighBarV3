# Contracts — Live Headless End-to-End

This directory holds the contract-shaped artifacts this feature
introduces or tightens. Unlike 001 (which shipped `.proto` contracts
for the RPC surface), 002 doesn't add new RPCs — its contracts are
the *observability formats* that acceptance scripts, CI, and external
tools assert against.

| File | What it pins |
|---|---|
| [unit-damaged-payload.md](./unit-damaged-payload.md) | Fields the gateway populates on `UnitDamagedEvent` and the engine-to-proto mapping. |
| [gateway-fault.md](./gateway-fault.md) | Structured `[hb-gateway] fault` log line + `highbar.health` file schema + gRPC trailer metadata. |
| [aicommand-arm-map.md](./aicommand-arm-map.md) | Per-arm wiring plus observability channel (state-stream / engine-log / lua-widget) for all 66 arms. |
| [aicommand-coverage-report.md](./aicommand-coverage-report.md) | CSV schema for `build/reports/aicommand-arm-coverage.csv`. |
| [ci-skip-reason.md](./ci-skip-reason.md) | Commit-trailer grammar for per-script skip waivers. |
| [build-runbook.md](./build-runbook.md) | Literate-markdown format for `BUILD.md` (expect-comment convention). |

All artifacts are GPL-2.0 along with the rest of the repo. Every
format below is consumed by at least one acceptance script or CI
job — nothing here is documentation-only.
