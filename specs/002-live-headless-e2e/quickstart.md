# Quickstart: Live Headless End-to-End

**Feature**: 002-live-headless-e2e
**Target**: get a maintainer on a clean reference host from checkout
to a running `spring-headless` match with an F# observer attached in
under 10 minutes (SC-001).

This quickstart is the skeleton that becomes the top-level
`BUILD.md` (FR-022). It is written in the literate-runbook format
described in
[contracts/build-runbook.md](./contracts/build-runbook.md): each
numbered step contains one `bash` block preceded by an
`<!-- expect: ... -->` comment, so
`tests/headless/build-runbook-validation.sh` can execute it verbatim
on a clean VM.

---

## Prerequisites

Reference host:

- Ubuntu 22.04 LTS x86_64
- `git`, `cmake ≥ 3.22`, `ninja-build`, `curl`, `bash ≥ 5`, `jq`, `nm`
- `buf ≥ 1.30` (proto codegen)
- `dotnet-sdk-8.0` (F# client)
- `python3.11` with `venv` and `pip`
- A vcpkg checkout at `$VCPKG_ROOT` (exported)
- `spring-headless` release `recoil_2025.06.19`, installed at
  `$HOME/.local/state/Beyond All Reason/engine/recoil_2025.06.19/spring-headless`
  with the BAR asset cache available (see
  `data/config/spring-headless.pin`)

If any prerequisite is missing, step 1 fails loudly before any build
work begins.

---

## 1. Pre-flight

<!-- expect: RUNBOOK-PREFLIGHT-OK -->

```bash
set -euo pipefail
# OS
grep -q "Ubuntu 22.04" /etc/os-release
# Tools
for t in git cmake ninja buf dotnet python3.11 jq nm; do
    command -v "$t" >/dev/null || { echo "missing $t"; exit 1; }
done
# Pinned engine
PIN_FILE=data/config/spring-headless.pin
test -f "$PIN_FILE"
ENGINE_PATH="$HOME/.local/state/$(grep install_path_relative "$PIN_FILE" | cut -d'"' -f2)/spring-headless"
test -x "$ENGINE_PATH"
# vcpkg
test -n "${VCPKG_ROOT:-}" && test -d "$VCPKG_ROOT"
echo RUNBOOK-PREFLIGHT-OK
```

---

## 2. Hydrate dependencies (vcpkg manifest)

<!-- expect: vcpkg manifest install complete -->

```bash
"$VCPKG_ROOT/vcpkg" install --x-manifest-root=. --x-install-root=./build/vcpkg_installed
echo "vcpkg manifest install complete"
```

Runs in <60 seconds on a warm vcpkg binary cache; first-time runs
may take several minutes (gRPC + Protobuf + Abseil source builds).

---

## 3. Proto codegen

<!-- expect: buf generated successfully -->

```bash
buf generate proto
echo "buf generated successfully"
```

Produces C++ stubs under `build/gen/highbar/v1/`, C# stubs under
`clients/fsharp/HighBar.Proto/generated/`, and Python stubs under
`clients/python/highbar_client/highbar/v1/`.

---

## 4. CMake configure

<!-- expect: Generating done -->

```bash
cmake --preset linux-release \
    -DCMAKE_TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake"
```

The `linux-release` preset sets `-fvisibility=hidden`, the gcc
symbol-map for `libSkirmishAI.so`, and the
`-DHIGHBAR_REQUIRE_WIRE_DEPS=ON` flag that makes the missing-gRPC
fallback a hard error (FR-002 — the previous `message(WARNING)`
branch at `CMakeLists.txt` lines 108–112 is replaced with
`message(FATAL_ERROR)`).

---

## 5. Build the plugin and tests

<!-- expect: libSkirmishAI.so -->

```bash
cmake --build --preset linux-release -j
ls build/libSkirmishAI.so
```

Builds `libSkirmishAI.so` plus every C++ unit-test executable in
`tests/unit/` (newly wired by this feature via `add_executable` +
`add_test`). Build completes within 15 minutes on the reference host
(FR-001 / US1 AC-1).

---

## 6. Unit tests (ctest)

<!-- expect: 100% tests passed -->

```bash
ctest --test-dir build --output-on-failure
```

Fails loudly if *zero* tests run (FR-016). The 7 files under
`tests/unit/` (ai_slot_test, command_queue_test,
command_validation_test, delta_bus_test, observer_permissions_test,
snapshot_builder_test, state_seq_invariants_test) are each a
separate `add_executable`/`add_test` pair, so `ctest` enumerates them
one by one.

---

## 7. F# client restore + build

<!-- expect: Build succeeded -->

```bash
dotnet build clients/fsharp/HighBar.Client.sln -c Release
```

Builds clean from a fresh `obj/` tree (FR-011: the first-build
glitch 001's verification pass observed — where `HighBar.Proto` did
not emit stubs until a second build — is a regression).

---

## 8. Python client codegen + editable install

<!-- expect: Successfully installed highbar-client -->

```bash
make -C clients/python codegen install-dev
```

The `make` target is a single-command entry point callable from the
repo root (FR-010). Under the hood it runs `grpc_tools.protoc` with
the right include paths to emit stubs into
`clients/python/highbar_client/highbar/v1/` (matching what the
client modules import — FR-009), then `pip install -e .[dev]` in
the repo's Python venv.

---

## 9. Launch `spring-headless`

<!-- expect: [hb-gateway] startup -->

```bash
bash tests/headless/_launch.sh \
    --start-script tests/headless/scripts/minimal.startscript \
    --plugin build/libSkirmishAI.so \
    --engine "$HOME/.local/state/Beyond All Reason/engine/recoil_2025.06.19/spring-headless" \
    --log /tmp/hb-engine.log \
    &
sleep 2
grep -q "\[hb-gateway\] startup" /tmp/hb-engine.log
test -S "/tmp/highbar.sock"  # UDS socket present
```

The plugin's startup log line `[hb-gateway] startup transport=uds
bound=/tmp/highbar.sock schema=highbar.v1` confirms that the plugin
loaded, the gateway started, and the UDS path is bound *before* the
first game frame (FR-003 / US1 AC-2).

---

## 10. Attach an F# observer and receive first snapshot

<!-- expect: first snapshot received -->

```bash
dotnet run --project clients/fsharp/samples/Observer \
    --configuration Release \
    --uds /tmp/highbar.sock \
    --token "$HOME/.spring/highbar.token" \
    --max-snapshots 1 \
    --timeout 2s
echo "first snapshot received"
```

The F# observer sample runs `Hello` → `StreamState`, waits for the
first `StateSnapshot`, prints a single-line summary
(`Snapshot: frame=... units=... enemies=...`), and exits. The
2-second timeout is the gate SC-001 names.

---

## After the runbook

At this point the maintainer has:

- a working `libSkirmishAI.so` on disk
- passing C++ unit tests
- a running `spring-headless` with the plugin loaded
- a bound UDS socket
- an F# observer that received a `StateSnapshot` within 2 seconds

Next, run the full acceptance suite:

```bash
# Observer path
bash tests/headless/us1-observer.sh

# AI command path
bash tests/headless/us2-ai-coexist.sh

# AI command arm coverage (66 arms, one pass each)
bash tests/headless/aicommand-arm-coverage.sh

# Framerate (deterministic seed)
bash tests/headless/us1-framerate.sh

# Latency (UDS)
bash tests/bench/latency-uds.sh

# Latency (TCP loopback)
bash tests/bench/latency-tcp.sh
```

Every one of these must exit 0 (not 77-skip) on the reference host
when this feature is complete. That is SC-002.

---

## Teardown

The gateway writes a health file at `$writeDir/highbar.health`.
Normal shutdown removes the token file and unlinks the socket; the
health file persists (diagnostic signal), and its `pid` field lets
any reader tell whether it reflects the current run. A
disabled-gateway health file (`status=disabled`) means the gateway
faulted — inspect the engine log for the matching
`[hb-gateway] fault subsystem=… reason=… …` line (format in
[contracts/gateway-fault.md](./contracts/gateway-fault.md)).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Step 4 fails with "gRPC not found" | `CMAKE_TOOLCHAIN_FILE` not set | Re-export `VCPKG_ROOT` and rerun step 4. |
| Step 5 emits `libSkirmishAI.so` but `nm` shows unexpected C++ symbols exported | symbol visibility regression | Re-check `CMakeLists.txt` keeps `-fvisibility=hidden` + the explicit symbol map; see `tests/headless/symbol-visibility-check.sh`. |
| Step 9 logs `[hb-gateway] fault subsystem=transport reason=eaddrinuse` | prior gateway still holds the UDS path | `rm /tmp/highbar.sock` and rerun; also verify no stale engine process: `pgrep spring-headless`. |
| Step 10 times out at 2s with no snapshot | `Hello` handshake mismatch | Compare `schema_version` in the plugin log vs F# client (should match `highbar.v1`). |
| `ctest` in step 6 reports zero tests ran | unit tests not wired into CMake | Re-check `CMakeLists.txt` `add_executable` targets for `tests/unit/*.cc`; this is FR-015 / FR-016. |

Any other failure not in this table is a bug; file it with the step
number, the expected substring that did not match, and the last 200
lines of output from the failing step's bash block.
