<!-- SPECKIT START -->
Active feature plan: [specs/001-grpc-gateway/plan.md](specs/001-grpc-gateway/plan.md).
See also the feature's research, data-model, contracts, and quickstart in the same
directory.
<!-- SPECKIT END -->

## Architecture

Read **[docs/architecture.md](docs/architecture.md)** first. It is the
authoritative reference and guidance document for HighBarV3's design.

HighBarV3 is a **fork of BARb (rlcevg/CircuitAI at commit
`0ef36267633d6c1b2f6408a8d8a59fff38745dc3`)**, the BAR-targeted Skirmish
AI plugin for the Recoil/Spring engine. V3 injects a new
`CGrpcGatewayModule : IModule` that exposes a gRPC server (Unix-domain
socket or loopback TCP), streams a materialized game state with deltas
to F#/.NET and Python clients, and routes external commands back into
the engine via CircuitAI's existing `CCircuitUnit::Cmd*` APIs.

License: **GPL-2.0** (inherited from CircuitAI).

Predecessor: `/home/developer/projects/HighBarV2` — hand-rolled
protobuf-over-UDS proxy, replaced by the gRPC design in V3. V2's
`proto/highbar/*.proto` messages are reused; V2's C proxy code is
discarded.

When making architectural or design decisions, consult
`docs/architecture.md` for the phased rollout, module integration
points, threading rules, transport config, and critical pitfalls.
