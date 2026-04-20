<!--
SYNC IMPACT REPORT
==================
Version change: (template placeholders) → 1.0.0
Rationale: Initial ratification. All principles and sections populated from
placeholders; MINOR/PATCH semantics do not apply to first adoption.

Modified principles: n/a (initial adoption)
Added principles (all new):
  I. Upstream Fork Discipline
  II. Engine-Thread Supremacy (NON-NEGOTIABLE)
  III. Proto-First Contracts
  IV. Phased Externalization
  V. Latency Budget as Shipping Gate

Added sections:
  - License & Compliance
  - Development Workflow & Quality Gates
  - Governance

Removed sections: none.

Templates status:
  ✅ .specify/templates/plan-template.md — "Constitution Check" gate already
     defers to this file; no edits needed.
  ✅ .specify/templates/spec-template.md — no constitution-driven mandatory
     sections to add; no edits needed.
  ✅ .specify/templates/tasks-template.md — task categorization unaffected;
     no edits needed.
  ✅ .specify/templates/checklist-template.md — scope unchanged; no edits
     needed.
  ✅ CLAUDE.md — already points implementers at docs/architecture.md, which
     is the runtime guidance document referenced from Governance.

Deferred TODOs: none.
-->

# HighBarV3 Constitution

## Core Principles

### I. Upstream Fork Discipline

HighBarV3 is a **fork** of BARb (rlcevg/CircuitAI at commit
`0ef36267633d6c1b2f6408a8d8a59fff38745dc3`), not a rewrite. Upstream
receives ongoing maintenance; our merge cost MUST stay low.

- All V3-specific code MUST live under dedicated paths reserved for the
  fork: `src/circuit/module/GrpcGatewayModule*`, `src/circuit/grpc/*`,
  `proto/highbar/*`, `clients/*`, `docs/*`, `vcpkg.json`,
  `data/config/grpc.json`.
- Edits to upstream-shared files (`src/circuit/CircuitAI.cpp`,
  `CMakeLists.txt`, build scripts) MUST be surgical: the smallest diff
  that achieves the goal. Each such edit MUST be justified in the PR
  description.
- Upstream merges are a named activity. They occur on a
  dedicated branch, preserve our isolated code paths, and MUST be
  accompanied by a full test run (unit + integration + headless) before
  landing on `main`.
- Rationale: keeping the seam between "ours" and "upstream" clean is
  what makes long-term maintenance possible. Sprawl here is the
  single largest long-term risk to the project.

### II. Engine-Thread Supremacy (NON-NEGOTIABLE)

Spring calls the Skirmish AI plugin from **one** thread. All CircuitAI
state mutations and all `CCircuitUnit::Cmd*` calls MUST execute on that
thread.

- gRPC worker threads MUST NOT touch CircuitAI managers, unit state,
  or the engine callback surface.
- External commands arriving on a gRPC worker MUST be enqueued to an
  MPSC queue and drained by the gateway module on the next frame-update
  callback.
- Snapshot serialization for new subscribers is the sole exception: it
  reads under a shared lock held from a worker thread. Writers take the
  lock exclusively; writers never block on gRPC I/O.
- Rationale: Spring's callback APIs are not documented as thread-safe.
  Violations produce rare, timing-dependent heisenbugs that cost days
  to diagnose. This principle is NON-NEGOTIABLE and any PR that breaks
  it is rejected on sight.

### III. Proto-First Contracts

Every client-observable interface lives in a `.proto` file under
`proto/highbar/`. There are no side-channel formats, no ad-hoc JSON,
no "just this once" string protocols.

- Schema changes MUST be backward-compatible within a MINOR release:
  field numbers preserved, type changes forbidden, removals only via
  explicit deprecation cycle (`deprecated = true` for at least one
  MINOR release before removal).
- Breaking schema changes require a MAJOR version bump of the
  `HighBarProxy` service and a migration plan for both F# and Python
  client shipments.
- Generated code (C++, C#, Python) is a build artifact of `buf`
  against `proto/highbar/`; it is never hand-edited and may be
  regenerated at any time.
- Rationale: the whole point of V3 is to make the transport
  language-agnostic and schema-stable. Out-of-band formats defeat that
  and must not be tolerated.

### IV. Phased Externalization

V3 reaches "external client IS the AI" incrementally. Each phase has a
gating criterion; phases advance on evidence, not on schedule.

- **Phase 1 (MVP)**: internal BARb modules active, gateway module
  additive. Default config `enable_builtin = true`. Gate to Phase 2:
  the gateway-only configuration passes headless-engine integration
  tests for N consecutive builds (N defined per release).
- **Phase 2**: `enable_builtin = false` supported. External client
  drives all decisions. Gate to Phase 3: demonstrated stable play in a
  full-length BAR match and a concrete use case asking for per-subsystem
  control.
- **Phase 3 (optional)**: per-module opt-out (`enable_military`,
  `enable_economy`, etc.). NOT delivered on speculation.
- Rationale: keeping the internal AI alive during transport work means
  every test run has a working baseline. If the gRPC path misbehaves,
  the game still plays, which makes regressions observable instead of
  catastrophic.

### V. Latency Budget as Shipping Gate

The V2 proxy hit sub-500µs round-trip; V3 does not regress that
characteristic. Latency is measured, not assumed.

- **Target**: p99 round-trip ≤ 500µs on UDS, ≤ 1.5ms on loopback TCP.
- **Measurement method**: `UnitDamaged` engine event → F# client
  `OnEvent` callback. Microbench lives alongside integration tests.
- Any change that pushes the microbench past budget is either
  reverted or accompanied by an explicit budget revision approved by
  the maintainer. "The benchmark is flaky" is not an acceptable
  justification; fix or stabilize it first.
- Rationale: latency is a product-defining attribute for AI bot
  transports. Regressions compound and are hard to recover from
  once shipped.

## License & Compliance

HighBarV3 inherits **GPL-2.0** from its upstream (CircuitAI). All
distributed artifacts are GPL-2.0 or GPL-2.0-compatible.

- Third-party dependencies MUST have GPL-2.0-compatible licenses.
  Permissively-licensed deps (MIT, Apache-2.0, BSD) are fine; copyleft
  incompatibilities (AGPL, SSPL) are not.
- Clients (`clients/fsharp/`, `clients/python/`) are considered
  "separate works" only to the extent that they communicate with the
  plugin via the defined gRPC interface and do not statically link
  GPL code. This condition MUST be preserved; clients that would
  require embedding V3 code are GPL-2.0 themselves.
- The generated proto code is a build artifact and inherits the
  license of the `.proto` files (GPL-2.0 within this repository).

## Development Workflow & Quality Gates

The project uses the SpecKit workflow: `constitution → specify →
clarify (optional) → plan → tasks → implement`.

- Each feature branch MUST originate from a `specify` and pass a
  `plan`'s Constitution Check before implementation work begins.
- Proto changes coordinate across three code-gen targets (C++, C#,
  Python). A PR touching `proto/highbar/*.proto` MUST update all three
  client-side stubs (or explicitly note a client is deferred, with a
  tracking issue).
- Tests are structured by scope: unit (no engine), integration
  (`dlopen`-driven mock engine), headless (real BAR engine). A PR
  affecting the gateway, state model, or transport MUST include or
  update at least one integration test.
- Upstream merges are gated by a full integration + headless pass.
- Commit hygiene: changes under `src/circuit/grpc/`,
  `src/circuit/module/GrpcGatewayModule*`, and `proto/highbar/*` SHOULD
  be commit-separated from any upstream-shared-file edits so upstream
  sync remains clean.

## Governance

This constitution supersedes any informal practice or tribal knowledge.
Where another document conflicts, the constitution wins; the conflicting
document is updated.

- **Amendments** require: (a) a PR modifying this file with a Sync
  Impact Report block, (b) a version bump per the versioning policy,
  and (c) updates to any dependent template or doc flagged by the
  report.
- **Versioning policy** (semantic):
  - MAJOR: a principle is removed or redefined in a backward-
    incompatible way, or governance rules change materially.
  - MINOR: a new principle or section is added, or guidance is
    materially expanded.
  - PATCH: clarifications, typo fixes, non-semantic refinements.
- **Compliance review**: every PR description MUST cite the
  principles it touches (typically by roman numeral). Reviewers
  validate compliance against this file before approving.
- **Runtime guidance**: implementers working on V3 consult
  `docs/architecture.md` for the authoritative design (module
  integration points, transport config, threading discipline,
  critical pitfalls). The constitution defines the *rules*; the
  architecture doc shows the *shape*.
- **Complexity justification**: any design that deviates from the
  architecture doc or a principle MUST be recorded in the feature
  plan's Complexity Tracking table, with a concrete reason a simpler
  alternative was rejected.

**Version**: 1.0.0 | **Ratified**: 2026-04-20 | **Last Amended**: 2026-04-20
