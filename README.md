# HighBarV3

HighBarV3 is a Beyond All Reason / Recoil Skirmish AI proxy. It embeds
a gRPC gateway in the BARb/CircuitAI plugin so external clients can
observe game state, submit AI commands, and run controlled admin/test
actions from any language with protobuf and gRPC support.

The native plugin remains the Spring/Recoil `libSkirmishAI.so`; built-in
BARb decision behavior is permanently disabled for HighBarV3 runs. The
external client is the decision authority.

## Start Here

- [Architecture](docs/architecture.md) explains the native plugin,
  gateway module, state stream, and engine-thread rules.
- [Transport](docs/transport.md) documents UDS/TCP transport options
  and local security assumptions.
- [Proto Reference](docs/proto-reference.md) lists every service,
  proto file, stream shape, auth metadata, and compatibility rule.
- [Client Development](docs/client-development.md) explains how to
  build clients in Python, F#/.NET, Go, Rust, Java/Kotlin, Node/TS, and
  other protobuf/gRPC stacks.
- [Python Client README](clients/python/README.md) covers the supported
  Python package, live topology launcher, BNV demos, and AI plugins.
- [Local Environment](docs/local-env.md) and [Build Hygiene](docs/commit-hygiene.md)
  cover local setup and repository workflow details.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `proto/highbar/*.proto` | Versioned `highbar.v1` wire contract. |
| `src/circuit/grpc/` | Native C++ gateway, admin controller, command validation, and snapshots. |
| `src/circuit/module/GrpcGatewayModule.*` | CircuitAI module that bridges engine events to gRPC. |
| `clients/python/` | Python package, generated stubs, samples, live topology launcher, and tests. |
| `clients/fsharp/` | F#/.NET client wrapper, samples, and latency bench. |
| `tests/headless/` | Live Recoil/BAR harness scripts, BNV demo reels, and shell acceptance tests. |
| `specs/` | Speckit feature specifications and contracts. |
| `.github/workflows/ci.yml` | Hosted and self-hosted CI pipeline. |

## Development Checks

The hosted GitHub workflow runs proto lint/generation smoke tests,
Python codegen/tests, shell syntax checks, and BUILD.md runbook
validation. Before pushing API/client changes, run the relevant local
subset:

```bash
buf lint proto
cd proto && buf generate
cd ../clients/python
python -m pip install -e '.[dev]'
make codegen
make test
```

For shell-only changes:

```bash
bash -n tests/headless/*.sh tests/bench/*.sh
```

Native build and live headless acceptance require a BAR/Recoil engine
checkout and the self-hosted runner environment described in
`.github/runner-setup/`.

## License

GPL-2.0-only, inherited from the BARb/CircuitAI fork.
