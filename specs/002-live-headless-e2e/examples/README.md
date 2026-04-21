# Client-mode reference scripts

These scripts are the reference implementation of the client-mode
relay pattern documented in
[`../investigations/hello-rpc-deadline-exceeded.md`](../investigations/hello-rpc-deadline-exceeded.md).

## `coordinator.py`

A Python gRPC server that hosts **both** sides of the relay:

- **Plugin-facing** (`HighBarCoordinator` service): the plugin dials
  in, sends heartbeats, streams `StateUpdate`s via `PushState`, and
  receives `CommandBatch`es via `OpenCommandChannel`.
- **Client-facing** (`HighBarProxy` service): external observers and
  AI-role clients dial in with exactly the same proto the plugin
  used to expose in server mode — so the F# and Python clients in
  `clients/*/` work unchanged against the coordinator.

Run it:

```bash
python3 coordinator.py --endpoint unix:/tmp/hb-coord.sock --id coord
```

Then start `spring-headless` with `HIGHBAR_COORDINATOR=unix:/tmp/hb-coord.sock`
in its env so the plugin knows where to dial.

## `observer.py`

A minimal observer that connects to the coordinator (not the plugin)
via `HighBarProxy.Hello` + `HighBarProxy.StreamState`, prints a
summary every 100 state updates, and exits after N messages.

```bash
python3 observer.py --endpoint unix:/tmp/hb-coord.sock --max 200
```

## End-to-end smoke

```bash
# terminal 1
python3 coordinator.py --endpoint unix:/tmp/hb-coord.sock --id coord

# terminal 2 (wait for coordinator to be up first)
HIGHBAR_COORDINATOR=unix:/tmp/hb-coord.sock \
SPRING_DATADIR="$HOME/.local/state/Beyond All Reason" \
spring-headless /path/to/match.startscript

# terminal 3 (once match is running)
python3 observer.py --endpoint unix:/tmp/hb-coord.sock --max 200
```

Observer prints lines like:

```
[obs] Hello OK session=coord-sess-1 current_frame=0
[obs rx=00001] seq=99  frame=2159 payload=delta delta_events=1
[obs rx=00101] seq=... frame=...  payload=delta delta_events=1
[obs] final: rx=200 last_seq=...
```
