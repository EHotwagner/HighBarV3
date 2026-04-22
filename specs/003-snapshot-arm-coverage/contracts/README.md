# Contracts: Snapshot-grounded behavioral verification of AICommand arms

**Feature**: 003-snapshot-arm-coverage
**Status**: Phase 1 output

The contracts below are the authoritative schemas the implementation
must honor. Each file specifies one interface or format:

| File | Audience | Scope |
|---|---|---|
| [`snapshot-tick.md`](./snapshot-tick.md) | Plugin & all clients | Proto surface: new `StateSnapshot.effective_cadence_frames` field and the plugin-side `snapshot_tick` config block. |
| [`request-snapshot.md`](./request-snapshot.md) | Plugin & all clients | Proto surface: new `HighBarProxy.RequestSnapshot` RPC. |
| [`arm-registry.md`](./arm-registry.md) | Python macro driver | Schema for the 66-row `BehavioralTestCase` registry, including the `required_capability` tag vocabulary and the `NotWireObservable` sentinel. |
| [`bootstrap-plan.md`](./bootstrap-plan.md) | Python macro driver | The deterministic 7-step bootstrap plan (FR-003a), its manifest, and the bootstrap-state reset protocol (FR-003b). |
| [`behavioral-coverage-csv.md`](./behavioral-coverage-csv.md) | Python macro driver & CI | CSV format at `build/reports/aicommand-behavioral-coverage.csv`, canonical digest serialization, and the `.digest` sidecar. |

Proto changes (`snapshot-tick.md`, `request-snapshot.md`) are purely
additive and backward-compatible within `highbar.v1` per Constitution
III. No existing field numbers are reused or renamed. Schema version
remains `1.0.0`.

The three driver-side contracts (registry, bootstrap, CSV) are Python-
internal formats, not wire protocols. They are documented here because
the CSV and digest are CI artifacts that downstream tooling (threshold
ratchet, reproducibility diff) consumes, and because the registry
schema determines the denominator of the coverage metric.
