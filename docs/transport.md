# Transport Selection

HighBarV3's gRPC gateway supports two transports: **Unix domain socket**
(default, lowest latency) and **loopback TCP** (for sandboxes /
containers / debuggers where UDS is unavailable). Switching between
them is a **one-line** change to `data/config/grpc.json` — client code,
client binary, and the proto schema are identical across transports
(SC-008).

## Switching transports

Edit `data/config/grpc.json`:

```json
{
  "transport": "uds",   // ← change to "tcp"
  "uds_path": "$XDG_RUNTIME_DIR/highbar-${gameid}.sock",
  "tcp_bind": "127.0.0.1:50511",
  "ai_token_path": "$writeDir/highbar.token",
  "max_recv_mb": 32,
  "ring_size": 2048
}
```

- `transport: "uds"` → bind the Unix domain socket at `uds_path`.
  `tcp_bind` is ignored.
- `transport: "tcp"` → bind loopback TCP at `tcp_bind`. `uds_path` is
  ignored.

That is the entire change. The plugin `libSkirmishAI.so`, the F#
`HighBar.Client` assembly, the `hb-observer` / `hb-ai` / `hb-latency`
binaries, and the Python client all work against both transports
without rebuild.

## Constraints

- **Loopback only.** `tcp_bind` must resolve to `127.0.0.0/8`, `::1`,
  or `localhost`. Non-loopback binds are rejected at plugin startup
  with a clear error — the spec assumes same-host deployment and the
  plugin fails-closed rather than silently exposing the gateway on
  the LAN.
- **UDS path length.** `uds_path` after `$VAR` expansion must be ≤108
  bytes (Linux `sun_path` limit). Longer paths fall back to
  `/tmp/hb-<short-hash>.sock` with a warning.
- **No TLS.** Both transports are plaintext. Confidentiality is
  delegated to the filesystem (UDS mode + token file 0600) and to the
  loopback-only TCP bind. There is no in-process trust boundary to
  encrypt.

## Latency budgets (Constitution V)

| Transport      | p99 round-trip gate |
|----------------|---------------------|
| UDS            | ≤ 500 µs            |
| Loopback TCP   | ≤ 1.5 ms            |

Measured via the `hb-latency` microbench against a live plugin. The CI
wrappers `tests/bench/latency-uds.sh` and `tests/bench/latency-tcp.sh`
exit non-zero when the gate is exceeded.

## When to prefer each

- **UDS (default)**: best latency, lowest overhead, process identity
  and filesystem ACLs enforce the trust boundary. Use this unless you
  have a specific reason not to.
- **TCP**: use when the environment cannot offer a shared filesystem
  namespace between the engine and the client — for example:
  - The client runs in a sibling container with no shared volume.
  - The engine runs inside a Flatpak/sandbox where the AI client
    cannot reach the sandbox's `$XDG_RUNTIME_DIR`.
  - A debugger or profiler that only speaks TCP.

## See also

- `data/config/grpc.json` — default config template.
- `specs/001-grpc-gateway/data-model.md` §6 `TransportEndpoint` —
  field-level validation rules.
- `specs/001-grpc-gateway/plan.md` §Technical Context — the same-host
  assumption and latency targets.
