# Quickstart — gRPC Gateway (feature `001-grpc-gateway`)

**Audience**: a developer who has just cloned the HighBarV3 fork and
wants to run the end-to-end happy path: plugin builds, match starts,
F# observer connects, AI client submits a `MoveTo`. Follow this exact
path before writing any new code — it is the reference "green" state.

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Status**: design-phase draft. Paths under `src/circuit/...` assume
`/speckit.implement` has produced the gateway module; before that,
the steps marked **(post-implement)** will not work.

---

## 0. Prerequisites

| Thing                 | Version / source                                                     |
|-----------------------|-----------------------------------------------------------------------|
| OS                    | Linux x86_64 (Ubuntu 22.04 reference)                                 |
| C++ toolchain         | GCC 12+ or Clang 15+ (C++20)                                         |
| CMake                 | 3.24+                                                                 |
| vcpkg                 | Checked out under `$VCPKG_ROOT`; manifest mode used, no global install |
| `buf`                 | 1.30+ (`go install github.com/bufbuild/buf/cmd/buf@latest`)          |
| .NET                  | 8.0 SDK (for F# client)                                               |
| Python                | 3.11+ (for Python client)                                             |
| BAR engine            | `spring-headless` matching BARb's target commit                        |
| BARb upstream         | Already present — HighBarV3 is the fork of `rlcevg/CircuitAI@0ef362…` |

Set `VCPKG_ROOT` and export it; CMake presets below expect it.

---

## 1. Build the plugin

```bash
cd /path/to/HighBarV3

# One-time: generate the proto sources into build/gen/
buf generate proto/

# Configure + build. vcpkg.json drives dep resolution.
cmake --preset linux-release \
      -DCMAKE_TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake"
cmake --build --preset linux-release -j
```

Output: `build/linux-release/libSkirmishAI.so` containing the BARb
base + the new `CGrpcGatewayModule`. Symbol-visibility flags
(`-fvisibility=hidden -Bsymbolic`) are already in the CMake target —
you do not need to add them.

Validate the gRPC/protobuf symbols are not leaked:

```bash
LD_DEBUG=symbols spring-headless --ai=HighBarV3 ... 2>&1 | grep -E '(grpc|protobuf)' | head
```

A handful of symbols resolving inside the `.so` is fine; any
cross-library resolution with the engine's own protobuf means
visibility is broken — fix before continuing. (Architecture doc
§Critical Pitfalls #3.)

---

## 2. Install the AI into BAR

```bash
cp build/linux-release/libSkirmishAI.so \
   ~/.config/spring/AI/Skirmish/HighBarV3/0.1.0/libSkirmishAI.so
cp data/config/grpc.json \
   ~/.config/spring/AI/Skirmish/HighBarV3/0.1.0/config/grpc.json
cp data/config/AIInfo.lua data/config/AIOptions.lua \
   ~/.config/spring/AI/Skirmish/HighBarV3/0.1.0/
```

`AIInfo.lua` preserves BARb's identity (short name `HighBarV3`,
display name as the fork names it) so operators can pick it in the
standard BAR game UI (FR-019).

---

## 3. Configure the transport

Default (UDS) works out of the box:

```json
// ~/.config/spring/AI/Skirmish/HighBarV3/0.1.0/config/grpc.json
{
  "grpc": {
    "transport":     "uds",
    "uds_path":      "$XDG_RUNTIME_DIR/highbar-${gameid}.sock",
    "tcp_bind":      "127.0.0.1:50511",
    "ai_token_path": "$writeDir/highbar.token",
    "max_recv_mb":   32,
    "ring_size":     2048
  }
}
```

To switch to loopback TCP (for container sandboxes — User Story 4):
change `"transport": "uds"` to `"transport": "tcp"`. No client-code
change (SC-008).

---

## 4. Launch a match with the plugin

Use `spring-headless` (faster than full Spring for smoke checks):

```bash
spring-headless /path/to/script.txt
```

The script selects `HighBarV3` as the AI for one slot. Look for these
log lines on stdout:

```
[HighBarV3] gateway bind uds=/run/user/1000/highbar-<gameid>.sock
[HighBarV3] token written to /…/highbar.token mode=0600
[HighBarV3] accepting connections
```

Phase 1 note: you will see BARb's existing internal modules logging
decisions alongside the gateway; that is correct — internal modules
remain active and the gateway is additive (Constitution IV).

---

## 5. Connect the F# observer

```bash
cd clients/fsharp
dotnet run --project samples/Observer -- \
    --endpoint unix:/run/user/1000/highbar-<gameid>.sock
```

Expected output within ~2 seconds (SC-001):

```
handshake ok schema=1.0.0 session=<uuid>
snapshot seq=1 frame=N own_units=M visible_enemies=K
delta    seq=2 frame=N+1 events=…
delta    seq=3 frame=N+2 events=…
…
```

The observer does not present a token and must not be required to
(FR-013). If you see `PERMISSION_DENIED` on `StreamState`, the auth
interceptor is over-enforcing — that's a bug, not a setup mistake.

---

## 6. Connect the F# AI client and submit a MoveTo

```bash
dotnet run --project samples/AiClient -- \
    --endpoint unix:/run/user/1000/highbar-<gameid>.sock \
    --token-file ~/.spring/write/highbar.token \
    --target-unit <unit-id-from-observer-log>
```

Expected behavior (User Story 2):

1. `Hello` succeeds; the AI session claims the exclusive AI slot.
2. A second concurrent AI-client attempt fails with
   `ALREADY_EXISTS` (FR-011). Verify by re-running the command while
   the first is still up.
3. `SubmitCommands` with `{ target_unit_id = <N>; move_to = (x, y, z) }`
   enqueues the order.
4. Within one game frame the unit begins moving — visible in the
   observer stream as an `EnemyEnterLOS` or positional update delta.

Measurement: run the latency microbench
(`dotnet run --project bench/Latency`) to confirm p99 round-trip
(`UnitDamaged` → `OnEvent`) is under the Constitution V budget:
500µs UDS, 1.5ms loopback TCP.

---

## 7. Connect the Python observer in parallel

```bash
cd clients/python
pip install -e .
python -m highbar_client.samples.observer \
    --endpoint unix:/run/user/1000/highbar-<gameid>.sock
```

With the F# observer still connected, both clients must see the
**same** sequence of `StateUpdate` messages. SC-004 is the acceptance
criterion; the spec's Independent Test for User Story 5 records both
streams to disk and asserts byte-equality for a 60-second window.

---

## 8. Exercise reconnect-with-resume

Start the F# observer, let it run for 30 seconds, kill it. Restart
with `--resume-from-seq <last-seen>`:

```bash
dotnet run --project samples/Observer -- \
    --endpoint unix:/run/user/1000/highbar-<gameid>.sock \
    --resume-from-seq <N>
```

Expected:

- If `N` is still inside the 2048-entry ring buffer, the next message
  has `seq == N+1` and the stream continues with no duplicates.
- If `N` is older than the ring allows, the server sends a
  `StateUpdate` with `payload = snapshot` and the client detects the
  reset from the discriminator (FR-008).

Never: a gap in `seq` values, or a duplicated `seq` value. SC-005's
checker fails either condition.

---

## 9. Phase-2 smoke (external-AI-only mode)

Edit the AI-options lua to set `enable_builtin = false`, relaunch:

```bash
# In ~/.config/spring/AI/Skirmish/HighBarV3/0.1.0/AIOptions.lua
{ key = "enable_builtin", value = "false", … }
```

Now no unit receives any order until your external AI sends one
(User Story 3). The AI slot stays alive with no built-in decisions;
if no external client ever connects, the match still plays (SC-007).

---

## 10. Observability

From an authenticated client (the AI client's token is fine), call
`GetRuntimeCounters`:

```bash
dotnet run --project samples/Counters -- \
    --endpoint unix:/run/user/1000/highbar-<gameid>.sock \
    --token-file ~/.spring/write/highbar.token
```

Fields to sanity-check:

- `subscriber_count` — matches the number of clients you have
  connected.
- `per_subscriber_queue_depth` — should be near-zero on a healthy
  run; sustained large values mean a slow consumer is about to be
  evicted.
- `frame_flush_time_us_p99` — rough health of the engine-thread
  fan-out path; watch this during Phase 2 when internal modules are
  off (load profile shifts).
- `command_submissions_rejected_resource_exhausted` — nonzero means
  you're flooding `SubmitCommands`. FR-012a intentionally surfaces
  this synchronously; the counter is the cumulative view.

Structured logs for connect/disconnect/eviction go to the engine's
log sink (FR-023); tail the engine log for those.

---

## 11. When something doesn't work

| Symptom                                                | First thing to check |
|--------------------------------------------------------|----------------------|
| Client can't find the token file                       | Race at startup. Client should retry for up to 5s (architecture doc §Critical Pitfalls #4). |
| `FAILED_PRECONDITION` on `Hello`                       | Schema mismatch; rebuild the client against the plugin's current `proto/highbar/`. |
| `RESOURCE_EXHAUSTED` at `Hello` for an observer        | Hit the cap of 4 (FR-015a). |
| `ALREADY_EXISTS` for a second AI client                | By design (FR-011) — only the first survives. |
| Stream closes with `RESOURCE_EXHAUSTED` mid-run        | Slow-consumer eviction. Your client is not draining; either speed up or reconnect with `resume_from_seq`. |
| `INTERNAL` on any RPC + AI slot reports failure to engine | Fail-closed (FR-003a). Gateway hit an unrecoverable fault; check engine log, file a bug. |
| UDS path bind fails with `ENAMETOOLONG`                | Path > 108 bytes; the plugin should have fallen back to `/tmp/hb-<hash>.sock`. If it didn't, `uds_path` resolution is broken. |
| Latency microbench over budget                         | Constitution V is a **gate**. Either revert the offending change or document a budget revision. "Benchmark is flaky" is not acceptable. |

---

## 12. Next steps after quickstart

- Read [`data-model.md`](./data-model.md) for the entity map before
  touching state-side code.
- Read [`contracts/README.md`](./contracts/README.md) for the
  per-RPC contract rules before touching the service impl.
- `/speckit.tasks` (Phase 2) produces the dependency-ordered build
  plan from this plan + research + data-model + contracts.
