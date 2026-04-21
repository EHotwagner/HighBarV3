# HighBarV3 Transport Configuration

The gateway exposes its gRPC surface over **one** of two transports,
selected at plugin startup from `data/config/grpc.json`. Both
transports are same-host only; the spec assumes the client and the
engine process are on the same machine.

## Selecting the transport

SC-008 calls for a single-line configuration change to swap
transports. In `data/config/grpc.json`:

```diff
 {
-  "transport": "uds",
+  "transport": "tcp",
   "uds_path":     "$XDG_RUNTIME_DIR/highbar-${gameid}.sock",
   "tcp_bind":     "127.0.0.1:50511",
   "ai_token_path": "$writeDir/highbar.token",
   "max_recv_mb":  32,
   "ring_size":    2048
 }
```

No client-code change is required. Both
[`clients/fsharp/src/Channel.fs`](../clients/fsharp/src/Channel.fs)
and the Python client pick up the transport string and build the
appropriate channel.

## UDS (default)

- **When to use**: local development, CI runners with filesystem
  access, same-namespace container sandboxes.
- **Performance**: ≤ 500µs p99 round-trip (Constitution V, SC-002).
- **Security**: the socket lives at the path in `uds_path` and
  inherits the directory's filesystem permissions. `$XDG_RUNTIME_DIR`
  is per-user and mode 0700 by default on modern distros.
- **Path limits**: Linux `sun_path` caps at 108 bytes. If the expanded
  path exceeds that, the plugin falls back to
  `/tmp/hb-<short-hash>.sock` and emits a warning.

## TCP (loopback only)

- **When to use**: container / sandbox setups where UDS bind-mounting
  is awkward, Windows clients talking to a Linux plugin host.
- **Performance**: ≤ 1.5ms p99 round-trip.
- **Bind validation**: the plugin rejects any `tcp_bind` host that is
  not `127.0.0.0/8` or `::1` at startup with a descriptive error.
  `localhost` / `ip6-localhost` are accepted as shorthands. This is a
  hard guard — the spec assumes same-host, and a non-loopback bind
  would expose the gateway with no TLS and a filesystem-anchored
  token. Fix `tcp_bind` or switch to UDS; there is no override.
- **Port defaults**: 50511 is the default dev port. Change
  `tcp_bind` to pick another.

## Verifying the toggle

After editing `grpc.json`, the plugin logs its chosen transport at
startup via `LogStartup`:

```
[hb-gateway] startup transport=tcp bind=127.0.0.1:50511 schema=1.0.0
```

End-to-end smoke tests:

- [`tests/headless/us1-observer.sh`](../tests/headless/us1-observer.sh) — default UDS path.
- [`tests/headless/us4-tcp.sh`](../tests/headless/us4-tcp.sh) — observer + AI submit over TCP.
- [`tests/headless/us4-transport-parity.sh`](../tests/headless/us4-transport-parity.sh) — byte-equal StateUpdate shape across both transports (SC-008 parity check).
- [`tests/bench/latency-uds.sh`](../tests/bench/latency-uds.sh) / [`latency-tcp.sh`](../tests/bench/latency-tcp.sh) — Constitution V gates per transport.

## What the config does NOT cover

- **TLS** — not implemented. The trust boundary is the same-host
  assumption plus the per-session AI token.
- **Cross-host TCP** — explicitly unsupported (see loopback guard above).
- **Multiple simultaneous transports** — the plugin binds exactly one
  transport per process.
