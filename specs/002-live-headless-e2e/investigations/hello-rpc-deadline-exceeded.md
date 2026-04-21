# Investigation — Hello RPC times out inside spring-headless

**Date**: 2026-04-21
**Status**: Open. Does not block the fault-tolerance track; blocks US1
Independent Test.

## Symptom

Inside a live `spring-headless` match running our built
`libSkirmishAI.so`, the gateway binds a UDS socket and writes the
token/health file successfully, but any gRPC client connecting to the
socket gets `grpc.StatusCode.DEADLINE_EXCEEDED` on `Hello` (same thing
for TCP loopback when `transport=tcp` is forced).

Reproducer:

```bash
SPRING_DATADIR="$HOME/.local/state/Beyond All Reason" \
XDG_RUNTIME_DIR="/tmp/hb-run" \
spring-headless /tmp/hb-run/match.startscript &

# Wait for socket at /tmp/hb-run/highbar-0.sock, then:
python3 -c "
import sys; sys.path.insert(0, '/tmp/hb-run/pyproto')
import grpc
from highbar import service_pb2, service_pb2_grpc
ch = grpc.insecure_channel('unix:///tmp/hb-run/highbar-0.sock')
stub = service_pb2_grpc.HighBarProxyStub(ch)
req = service_pb2.HelloRequest(schema_version='1.0.0', role=service_pb2.Role.ROLE_OBSERVER)
print(stub.Hello(req, timeout=5))
"
# → DEADLINE_EXCEEDED
```

## Confirmed

- `[hb-gateway] startup` log line lands (startup banner is wired).
- `bind(fd, AF_UNIX, /tmp/hb-run/highbar-0.sock)` and `listen(fd, 4096)`
  both succeed (strace).
- gRPC creates a dedicated epoll fd (e.g., fd 18) and registers our
  listen fd with `EPOLL_CTL_ADD, fd=20, events=EPOLLIN|EPOLLOUT|EPOLLET`.
- A gRPC worker thread blocks in `epoll_wait(18, …)` — it's alive and
  polling.
- Our `CqWorker` thread blocks in `grpc_completion_queue_next(cq, …)`
  with infinite deadline (confirmed via `GRPC_TRACE=api,http`).
- **Zero** `accept4()` syscalls in the entire trace, even while the
  client's `connect()` is hanging.

## Ruled out

- Not UDS-specific: forcing `transport=kTcp` in `Config.h` (default)
  produced the same DEADLINE_EXCEEDED on `127.0.0.1:50511`.
- Not our client: the same Python client gets `SUCCESS` against a
  Python `grpcio` server on the same UDS path.
- Not our gRPC vcpkg build: a minimal standalone C++ server linked
  against the exact same `vcpkg_installed/x64-linux` libraries
  responds to `Hello` perfectly.
- Not the CqWorker (our code): it is scheduled and blocks on Next as
  expected.
- Not `EventEngine` experiments:
  `GRPC_EXPERIMENTS=-event_engine_listener,-event_engine_client,-event_engine_for_all_other_endpoints,-event_engine_dns,-event_engine_dns_non_client_channel,-event_engine_callback_cq`
  + `GRPC_POLL_STRATEGY=epoll1` + `GRPC_ENABLE_FORK_SUPPORT=false`
  did not change behaviour.

## Current hypothesis

Static-link symbol pollution. Our `libSkirmishAI.so`:

```
$ nm -D --defined-only libSkirmishAI.so | grep -c " T "
16599
```

16 599 exported text symbols. Among them is the full OpenSSL surface
(`ASN1_*`, `ACCESS_DESCRIPTION_*`, `EVP_*`, `X509_*`, …) pulled in by
gRPC → absl → openssl in the vcpkg dep graph.

`CMakeLists.txt` only applies `-fvisibility=hidden` to our own
translation units; it does not set `-Wl,--exclude-libs,ALL` or a
linker version script, so static-lib symbols are exported by default.
Spring's runtime libraries (LuaSocket, NetProto) dlopen their own
libssl; at RTLD resolve time there are now two copies of the same
symbols in the same address space. gRPC's internals (thread-local
state, event engine poll-set registration) may be pointing at one
copy while the running polling thread was set up against the other —
consistent with "epoll_wait(fd=18) runs forever but accept4 never
happens because the fd registration is on a different pollset instance."

## Experiments run (2026-04-21)

All four ruled the hypothesis *out* — the symptom is still
DEADLINE_EXCEEDED. The bug has narrowed to "gRPC's EventEngine poller
does not deliver kernel accept-ready events while running inside
spring-headless's process."

### Experiment T022 — symbol visibility

Added `-Wl,--exclude-libs,ALL` to the shared-lib linker flags (see
`CMakeLists.txt`). Dropped exported T-symbols from 16 599 → 3
(C-ABI entry points only). Full vcpkg grpc/protobuf/absl/openssl
surface no longer leaks. **Did not fix the timeout.** Symbol collision
ruled out.

### Experiment 2 — defer Bind() to OnFrameTick frame ≥ 30

Moved `service_->Bind()` out of the ctor and into `OnFrameTick` gated
on `frame_id_ >= 30`. The match **never reached frame 0** (sat at
`f=-000001` for the entire 45s timeout, no frame advance, then SIGSEGV
on kill). Deferring the bind evidently blocks some part of spring's
AI initialization from completing. Reverted.

### Experiment 1 — sync server instead of async CallData

Replaced `HighBarService : AsyncService` with `HighBarService : Service`
and a direct `Status Hello(...)` override (no CQ, no CallData, gRPC
manages its own threads). Gateway binds, startup banner fires, Python
`Hello` still gets DEADLINE_EXCEEDED. **Sync-vs-async ruled out.**
Restored async.

### Experiment 3 — reset signal mask + sigmask before BuildAndStart

Called `pthread_sigmask(SIG_SETMASK, &empty, nullptr)` right before
`builder.BuildAndStart()` so gRPC's children inherit a clean signal
mask. Same DEADLINE_EXCEEDED. **Signal-mask inheritance ruled out.**

## Definitive findings from strace

Under a clean `strace -f -e trace=clone3,%network,epoll_*,listen,accept,accept4`:

- `bind(fd, AF_UNIX, highbar-0.sock) = 0` ✓
- `listen(fd, 4096) = 0` ✓
- `epoll_ctl(epoll_fd, EPOLL_CTL_ADD, listen_fd, EPOLLIN|EPOLLOUT|EPOLLET)
  = 0` ✓ (sync server registers listen fd on the epoll; async doesn't —
  that's a separate issue)
- `epoll_wait(epoll_fd <unfinished...>)` — gRPC's poll thread is
  correctly blocked on the right epoll fd.
- **Zero `accept4()` calls in the entire process lifetime.**
- **Zero `epoll_wait` returns** even when a client connects.
- `ss -x state all` shows `Recv-Q=1` on the listen socket when a
  client is mid-connect — the kernel IS queueing the connection.
- Python reproduction — `socket(UNIX) + bind + listen +
  epoll.register(EPOLLIN|EPOLLOUT|EPOLLET) + epoll.poll(5)` with an
  external `socat` connector — **fires correctly** and `accept()`
  succeeds. Kernel-level EPOLLET on UNIX listen is fine.
- Standalone C++ server built with the same vcpkg libs — **works
  end-to-end**, 24 epoll_wait cycles, 2 accept4, SUCCESS reply.

## Conclusion

The gRPC 1.76 EventEngine poller, when running inside `spring-headless`,
silently fails to deliver kernel-queued accept-ready events to its
epoll waiter. The registration is correct, the thread is alive, the
kernel queue has the connection — the notification is simply lost.

The `GRPC_EXPERIMENTS="-event_engine_listener,…"` env-var disable path
was attempted but vcpkg 1.76 reports the experiments as hard-enabled
anyway (see `gRPC experiments enabled: …event_engine_listener…` in the
log), so the legacy iomgr poller can't be selected at runtime.

## Remaining options

1. **Architectural flip — plugin becomes a gRPC client** (user's
   suggestion). Outbound `connect()` sidesteps the server-side
   EventEngine listener path entirely. Significant refactor, but the
   one remaining clean path.
2. Recompile gRPC from source with EventEngine disabled at compile
   time (`GRPC_DISABLE_EVENT_ENGINE=ON` or equivalent CMake option).
   Would require a bespoke vcpkg port. Another ~30 min build on top
   of the 39 min already spent on the default port.
3. Downgrade to pre-1.50 gRPC that predates EventEngine. Binary
   incompatibility with existing vcpkg baseline pin — substantial
   vcpkg.json work.
4. Deep-dive into the EventEngine poller. Not cheap — requires gRPC
   internals familiarity.

Option 1 is now the recommended path.

## Evidence files

- `/tmp/hb-run/strace.out`, `strace-sync.out`, `strace-fresh.out`,
  `strace-standalone.out` — traces from each experiment
- `/tmp/hb-run/match-trace.log`, `match-sync-str.log` — server-side
  gRPC TRACE=api,http,event_engine output
- `/tmp/hb-run/match-exp1.log`, `match-exp2.log`, `match-exp3.log` —
  experiment match logs
- `/tmp/hb-standalone/build/hb_server` — control server that works
  (proves vcpkg libs, proto, and our service code are fine)
- `/tmp/epoll-test.py` — Python EPOLLET+UNIX-listen control (works)
