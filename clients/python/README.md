# HighBar Python Client

Python 3.11+ client for the HighBarV3 gRPC gateway.

## Install (dev)

```bash
cd clients/python
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Generate proto stubs into highbar_client/ (writes *_pb2.py and *_pb2_grpc.py).
python -m grpc_tools.protoc \
    -I../../proto \
    --python_out=highbar_client \
    --grpc_python_out=highbar_client \
    ../../proto/highbar/*.proto
```

The generated files are `.gitignore`d — regenerate them after any
`proto/highbar/*.proto` change.

## Usage

```python
from highbar_client import channel, session, state_stream

ch = channel.for_endpoint(channel.Endpoint.uds('/run/user/1000/highbar-1.sock'))
hs = session.hello(ch, role=session.ClientRole.OBSERVER, client_id='my-tool/0.1.0')
print('connected', hs.session_id, 'schema', hs.schema_version)

for update in state_stream.consume(ch, resume_from_seq=0):
    print(update.seq, update.frame)
```

AI role:

```python
from highbar_client import commands

token = session.read_token_with_backoff('/path/to/highbar.token', max_delay_ms=5000)
hs = session.hello(ch, role=session.ClientRole.AI, client_id='my-ai/0.1.0', token=token)
batch = commands.batch(target_unit=42, batch_seq=1,
                       orders=[commands.move_to(1024.0, 0.0, 1024.0)])
ack = commands.submit_one(ch, token, batch)
```
