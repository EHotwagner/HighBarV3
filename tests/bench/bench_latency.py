#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# HighBarV3 — latency bench (T062, T063).
#
# Measures p99 round-trip from the plugin's CoordinatorClient::
# PushStateUpdate (which stamps StateUpdate.send_monotonic_ns at the
# moment Write() is called on the gRPC stream) to the client-side
# receipt of that same StateUpdate after fan-out through the
# coordinator.
#
# Methodology:
#   - Subscribe via HighBarProxy.StreamState.
#   - For each StateUpdate with send_monotonic_ns != 0:
#         observed_us = (recv_monotonic_ns - send_monotonic_ns) / 1000
#     (Both clocks are CLOCK_MONOTONIC on the same host; comparable
#      so long as bench runs co-located with plugin + coordinator.)
#   - Collect until --samples reached OR --duration-sec elapsed.
#   - Report p50/p99/max; exit 1 if p99 > budget, else 0.
#
# This intentionally measures the full plugin→coordinator→client
# datapath (the user-visible round trip) — per-hop decomposition
# would need additional timestamps the proto does not currently
# carry.
#
# Exit codes:
#   0  — p99 within budget.
#   1  — p99 exceeded budget.
#   77 — gateway unreachable / insufficient samples.

import argparse
import os
import sys
import time

import grpc

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "clients", "python", "highbar_client"))

from highbar import service_pb2, service_pb2_grpc  # noqa: E402


def percentile(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = max(0, min(len(s) - 1, int(len(s) * p) - (1 if p == 1.0 else 0)))
    return s[idx]


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transport", choices=("uds", "tcp"), required=True)
    ap.add_argument("--endpoint", required=True,
                    help="UDS path or TCP host:port reachable as coordinator")
    ap.add_argument("--duration-sec", type=int, default=30)
    ap.add_argument("--samples", type=int, default=1000)
    ap.add_argument("--budget-us", type=float, required=True)
    ap.add_argument("--output", default=None,
                    help="file to write 'p99=<us>' into on success")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    if args.transport == "uds":
        channel = grpc.insecure_channel(f"unix:{args.endpoint}")
    else:
        channel = grpc.insecure_channel(args.endpoint)

    try:
        grpc.channel_ready_future(channel).result(timeout=5.0)
    except grpc.FutureTimeoutError:
        print(f"bench: coordinator not reachable on {args.transport} "
              f"{args.endpoint} — SKIP", file=sys.stderr)
        return 77

    stub = service_pb2_grpc.HighBarProxyStub(channel)

    hello = service_pb2.HelloRequest(
        schema_version="1.0.0",
        role=service_pb2.HelloRequest.ROLE_OBSERVER,
        client_name="hb-latency-bench",
    )
    try:
        stub.Hello(hello, timeout=5.0)
    except grpc.RpcError as e:
        print(f"bench: Hello failed: {e.code().name} — SKIP", file=sys.stderr)
        return 77

    samples_us = []
    damaged_invalid = 0  # T065: UnitDamaged with damage<=0 or all-zero dir
    damaged_total = 0
    stream = stub.StreamState(
        service_pb2.StreamStateRequest(resume_from_seq=0),
        timeout=args.duration_sec + 5,
    )
    deadline = time.monotonic() + args.duration_sec

    try:
        for update in stream:
            # T065: opportunistic damage-payload validation. The
            # widening (T058-T061) is feature-gated by C++ types so
            # any incoming UnitDamaged with zero damage or all-zero
            # direction means the engine plumbing regressed.
            if update.WhichOneof("payload") == "delta":
                for ev in update.delta.events:
                    if ev.WhichOneof("kind") == "unit_damaged":
                        damaged_total += 1
                        d = ev.unit_damaged
                        dir_ok = (d.direction.x != 0.0
                                  or d.direction.y != 0.0
                                  or d.direction.z != 0.0)
                        if d.damage <= 0.0 or not dir_ok:
                            damaged_invalid += 1

            if update.send_monotonic_ns == 0:
                continue
            now_ns = time.monotonic_ns()
            dt_us = (now_ns - update.send_monotonic_ns) / 1000.0
            if dt_us < 0 or dt_us > 1_000_000:
                # clocks skewed or proxy-introduced delay outside
                # latency scope; drop rather than bias the tail.
                continue
            samples_us.append(dt_us)
            if len(samples_us) >= args.samples:
                break
            if time.monotonic() >= deadline:
                break
    except grpc.RpcError as e:
        print(f"bench: stream broken: {e.code().name}", file=sys.stderr)

    if damaged_invalid > 0:
        print(f"bench: FAIL — {damaged_invalid}/{damaged_total} UnitDamaged "
              f"events had damage<=0 or all-zero direction (T065 widening "
              f"regression)", file=sys.stderr)
        return 1

    if len(samples_us) < 10:
        print(f"bench: only {len(samples_us)} samples (need ≥10) — SKIP",
              file=sys.stderr)
        return 77

    p50 = percentile(samples_us, 0.50)
    p99 = percentile(samples_us, 0.99)
    mx = max(samples_us)
    print(f"bench: transport={args.transport} samples={len(samples_us)} "
          f"p50={p50:.1f}µs p99={p99:.1f}µs max={mx:.1f}µs "
          f"budget={args.budget_us:.1f}µs")

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(f"transport={args.transport}\n")
            f.write(f"samples={len(samples_us)}\n")
            f.write(f"p50_us={p50:.1f}\n")
            f.write(f"p99_us={p99:.1f}\n")
            f.write(f"max_us={mx:.1f}\n")
            f.write(f"budget_us={args.budget_us:.1f}\n")

    if p99 > args.budget_us:
        print(f"bench: FAIL p99 {p99:.1f}µs exceeds {args.budget_us:.1f}µs",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
