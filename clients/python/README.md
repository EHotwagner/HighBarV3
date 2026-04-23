# HighBar Python Client

Python 3.11+ client for the HighBarV3 gRPC gateway.

## Install (dev)

```bash
cd clients/python
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Regenerate gRPC stubs into highbar_client/highbar/.
make codegen
```

`make codegen` runs `python -m grpc_tools.protoc` with the right
include paths — it picks up every `proto/highbar/*.proto` and writes
`*_pb2.py` / `*_pb2_grpc.py` under `highbar_client/highbar/`. Other
targets:

| `make` target | What it does                                         |
|---------------|------------------------------------------------------|
| `codegen`     | regenerate stubs (above)                             |
| `install-dev` | `pip install -e '.[dev]'`                            |
| `test`        | run pytest                                           |
| `clean`       | remove generated stubs + `__pycache__`               |

The generated files **are committed** under
`highbar_client/highbar/` (per T036) so users do not need a
`grpcio-tools` install just to import the package; only contributors
who change `.proto` files need to run `make codegen`.

## Live-gateway environment

The acceptance grid scripts (`tests/headless/*.sh`) and the latency
bench (`tests/bench/latency-{uds,tcp}.sh`) read these env vars:

| Var                    | Used by                       | Notes                                                 |
|------------------------|-------------------------------|-------------------------------------------------------|
| `SPRING_HEADLESS`      | `_launch.sh`, every script    | Path to the pinned spring-headless binary. Skip-77 if unset. |
| `HIGHBAR_COORDINATOR`  | `_launch.sh`                  | Coordinator endpoint the plugin dials (e.g. `unix:/tmp/hb-coord.sock`). |
| `HIGHBAR_WRITE_DIR`    | `_fault-assert.sh`, drivers   | Directory where the plugin writes `highbar.health`. Defaults to `$HOME/.local/state/Beyond All Reason`. |
| `HIGHBAR_BENCH_DURATION` | `latency-{uds,tcp}.sh`      | Bench window in seconds. Default 30.                  |
| `HIGHBAR_BENCH_SAMPLES`  | `latency-{uds,tcp}.sh`      | Hard cap on sample count. Default 1000.               |
| `HIGHBAR_TCP_BIND`     | `latency-tcp.sh`              | Coordinator TCP bind address. Default `127.0.0.1:50521`. |

Note the architecture flip vs. earlier docs: the plugin is a gRPC
**client**, not a server. There is no `HIGHBAR_UDS_PATH` or
`HIGHBAR_TOKEN_PATH` in this revision — the plugin dials the
coordinator at `HIGHBAR_COORDINATOR`, so the only on-disk artifact
is the `highbar.health` JSON file.

## Usage (observer)

```python
import grpc
from highbar import service_pb2, service_pb2_grpc

ch = grpc.insecure_channel('unix:/tmp/hb-coord.sock')
stub = service_pb2_grpc.HighBarProxyStub(ch)

hello = stub.Hello(service_pb2.HelloRequest(
    schema_version='1.0.0',
    role=service_pb2.Role.ROLE_OBSERVER,
    client_id='my-tool/0.1.0',
))
print('connected', hello.session_id, 'schema', hello.schema_version)

for update in stub.StreamState(
    service_pb2.StreamStateRequest(resume_from_seq=0)
):
    print(update.seq, update.frame)
```

## Usage (AI role)

```python
from highbar import service_pb2, service_pb2_grpc, commands_pb2

stub = service_pb2_grpc.HighBarProxyStub(ch)
stub.Hello(service_pb2.HelloRequest(
    schema_version='1.0.0',
    role=service_pb2.Role.ROLE_AI,
    client_id='my-ai/0.1.0',
))

batch = commands_pb2.CommandBatch(batch_seq=1)
mv = batch.commands.add().move_unit
mv.unit_id = 42
mv.target.x = 1024.0
mv.target.y = 0.0
mv.target.z = 1024.0
ack = stub.SubmitCommands(iter([batch]))
print('ack', ack.batches_accepted)
```

See `specs/002-live-headless-e2e/examples/{observer,ai_client}.py`
for runnable end-to-end demos.

## Python AI plugins

The Spring-side Skirmish AI remains the native `highBar` proxy. Python
AI plugins are external policies that connect through `HighBarProxy` as
`ROLE_AI`, consume `StreamState`, and submit command batches back through
the same proxy.

Run a built-in policy:

```bash
hb-ai-runner-py \
  --transport uds \
  --uds-path /tmp/hb-run/highbar-1.sock \
  --token-file /tmp/highbar.token \
  --ai-plugin idle \
  --name-addon scout-a
```

Run a smoke movement policy:

```bash
hb-ai-runner-py \
  --transport uds \
  --uds-path /tmp/hb-run/highbar-1.sock \
  --token-file /tmp/highbar.token \
  --ai-plugin move-once \
  --plugin-config '{"target_unit":42,"move_to":"1024,0,1024"}' \
  --name-addon flank-test
```

Run the defensive macro policy:

```bash
hb-ai-runner-py \
  --transport uds \
  --uds-path /tmp/hb-run/highbar-1.sock \
  --token-file /tmp/highbar.token \
  --ai-plugin turtle1 \
  --name-addon turtle1-a
```

`turtle1` resolves BAR unit names through callbacks, checks each
builder's runtime build options, then builds economy, defenses,
factories, tech, and a mixed army near its own start area. It does not
emit enemy-directed move, fight, patrol, or attack commands.

Load a custom policy with `module:factory`:

```python
from collections.abc import Iterable

from highbar_client.ai_plugins import AIPluginContext, BaseAIPlugin
from highbar_client.highbar import commands_pb2, state_pb2


class MyPolicy(BaseAIPlugin):
    name = "my-policy"
    version = "0.1.0"

    def on_state(
        self,
        context: AIPluginContext,
        update: state_pb2.StateUpdate,
    ) -> Iterable[commands_pb2.CommandBatch]:
        return ()


def create(config):
    return MyPolicy()
```

Then run `hb-ai-runner-py --ai-plugin my_module:create ...`.
`--name-addon` is sanitized and appended to the gRPC `client_id`, so
multiple Python policies running through the same unchanged proxy can be
distinguished in coordinator logs.
