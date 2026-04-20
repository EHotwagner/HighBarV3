#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""HighBarV3 Python AI-role sample (T090).

Python analog of the F# AiClient sample. Reads the token with
exponential backoff, performs an AI-role Hello, then submits one
CommandBatch containing a MoveTo.

Run:
    python -m samples.ai_client --target-unit 42 --move-to 1024,0,1024
"""

from __future__ import annotations

import argparse
import os
import sys

from highbar_client import channel as hb_channel
from highbar_client import commands as hb_cmd
from highbar_client import session as hb_session


def parse_vec(s: str) -> tuple[float, float, float]:
    parts = s.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"--move-to expects x,y,z (got {s!r})"
        )
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="hb-ai")
    p.add_argument("--transport", default="uds", choices=["uds", "tcp"])
    p.add_argument(
        "--uds-path",
        default=os.path.join(
            os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "highbar-1.sock"
        ),
    )
    p.add_argument("--tcp-bind", default="127.0.0.1:50511")
    p.add_argument("--max-recv-mb", type=int, default=32)
    p.add_argument(
        "--token-file",
        default=os.path.join(os.environ.get("HOME", ""), "highbar.token"),
    )
    p.add_argument("--target-unit", type=int, required=True)
    p.add_argument("--move-to", type=parse_vec, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    endpoint = hb_channel.parse(args.transport, args.uds_path, args.tcp_bind)
    channel = hb_channel.for_endpoint(endpoint, max_recv_mb=args.max_recv_mb)

    hs, token = hb_session.hello_ai(
        channel,
        client_id="hb-python-ai/0.1.0",
        token_path=args.token_file,
    )
    print(f"connected  session={hs.session_id}  frame={hs.current_frame}", flush=True)

    if args.move_to is None:
        ai_cmd = hb_cmd.stop(args.target_unit)
    else:
        x, y, z = args.move_to
        ai_cmd = hb_cmd.move_to(args.target_unit, x, y, z)

    batch = hb_cmd.batch(1, args.target_unit, ai_cmd)
    ack = hb_cmd.submit(channel, token, [batch])

    print(
        f"ack  accepted={ack.batches_accepted} "
        f"rejected_invalid={ack.batches_rejected_invalid} "
        f"rejected_full={ack.batches_rejected_full} "
        f"last_seq={ack.last_accepted_batch_seq}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
