#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""HighBarV3 Python observer sample (T088).

Matches quickstart.md §7 — connects to the gateway over UDS or TCP,
performs the Hello handshake, then prints one line per StateUpdate
until Ctrl-C.

Run:
    python -m samples.observer --transport uds \\
        --uds-path "$XDG_RUNTIME_DIR/highbar-1.sock"
"""

from __future__ import annotations

import argparse
import os
import signal
import sys

from highbar_client import channel as hb_channel
from highbar_client import session as hb_session
from highbar_client import state_stream as hb_stream


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="hb-observer")
    p.add_argument("--transport", default="uds", choices=["uds", "tcp"])
    p.add_argument(
        "--uds-path",
        default=os.path.join(
            os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "highbar-1.sock"
        ),
    )
    p.add_argument("--tcp-bind", default="127.0.0.1:50511")
    p.add_argument("--max-recv-mb", type=int, default=32)
    p.add_argument("--resume-from-seq", type=int, default=0)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    endpoint = hb_channel.parse(args.transport, args.uds_path, args.tcp_bind)
    channel = hb_channel.for_endpoint(endpoint, max_recv_mb=args.max_recv_mb)

    hs = hb_session.hello(channel, role="observer", client_id="hb-python-observer/0.1.0")
    print(
        f"connected  session={hs.session_id}  "
        f"schema={hb_session.SCHEMA_VERSION}  frame={hs.current_frame}",
        flush=True,
    )
    print(
        f"static_map cells={hs.static_map.width_cells}x"
        f"{hs.static_map.height_cells} "
        f"metal_spots={len(hs.static_map.metal_spots)}",
        flush=True,
    )

    def _sigint(_sig, _frm):
        channel.close()

    signal.signal(signal.SIGINT, _sigint)

    try:
        for upd in hb_stream.consume(channel, resume_from_seq=args.resume_from_seq):
            arm = upd.WhichOneof("payload")
            if arm == "snapshot":
                print(
                    f"seq={upd.seq} frame={upd.frame} SNAPSHOT "
                    f"own={len(upd.snapshot.own_units)} "
                    f"enemies={len(upd.snapshot.visible_enemies)}",
                    flush=True,
                )
            elif arm == "delta":
                print(
                    f"seq={upd.seq} frame={upd.frame} DELTA "
                    f"events={len(upd.delta.events)}",
                    flush=True,
                )
            elif arm == "keepalive":
                print(f"seq={upd.seq} frame={upd.frame} KEEPALIVE", flush=True)
            else:
                print(f"seq={upd.seq} unknown payload", flush=True)
    except KeyboardInterrupt:
        print("canceled.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
