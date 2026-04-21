#!/usr/bin/env python3
"""Observer — connects to the coordinator via the HighBarProxy service,
subscribes to state updates, prints summary every N messages."""
import sys
import argparse
sys.path.insert(0, "/tmp/hb-run/pyproto")
import grpc
from highbar import service_pb2, service_pb2_grpc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", required=True)
    p.add_argument("--max", type=int, default=20)
    args = p.parse_args()

    ch = grpc.insecure_channel(args.endpoint)
    stub = service_pb2_grpc.HighBarProxyStub(ch)

    # Hello first
    hello = stub.Hello(service_pb2.HelloRequest(
        schema_version="1.0.0",
        role=service_pb2.Role.ROLE_OBSERVER,
    ), timeout=5)
    print(f"[obs] Hello OK session={hello.session_id} "
          f"current_frame={hello.current_frame}", flush=True)

    # Subscribe to state
    req = service_pb2.StreamStateRequest(resume_from_seq=0)
    n = 0
    last_seq = 0
    damaged_events = 0
    damaged_invalid = 0  # T065: count UnitDamaged with 0 damage or all-zero dir
    try:
        for update in stub.StreamState(req, timeout=300):
            n += 1
            last_seq = update.seq
            if update.WhichOneof("payload") == "delta":
                for ev in update.delta.events:
                    if ev.WhichOneof("kind") == "unit_damaged":
                        d = ev.unit_damaged
                        damaged_events += 1
                        dir_ok = (d.direction.x != 0.0
                                  or d.direction.y != 0.0
                                  or d.direction.z != 0.0)
                        if d.damage <= 0.0 or not dir_ok:
                            damaged_invalid += 1
            if n % 100 == 1 or n <= 3:
                which = update.WhichOneof("payload")
                ndelta = (len(update.delta.events)
                          if which == "delta" else 0)
                print(f"[obs rx={n:05d}] seq={update.seq} frame={update.frame} "
                      f"payload={which} delta_events={ndelta}", flush=True)
            if n >= args.max:
                break
    except grpc.RpcError as e:
        print(f"[obs] stream ended: code={e.code().name}", flush=True)
    print(f"[obs] final: rx={n} last_seq={last_seq} "
          f"damaged={damaged_events} damaged_invalid={damaged_invalid}",
          flush=True)
    if damaged_invalid > 0:
        # Non-fatal for a pure observer, but flag loudly so the driver
        # script can fail the test (contracts/unit-damaged-payload.md).
        print(f"[obs] WARN: {damaged_invalid} UnitDamaged events had "
              f"damage<=0 or all-zero direction", flush=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
