# SPDX-License-Identifier: GPL-2.0-only
"""Python AI-role sample (T090). Parallel to clients/fsharp/samples/AiClient."""

from __future__ import annotations

import argparse
import os
import sys

import grpc

from .. import channel, commands, session


def _default_uds_path() -> str:
    return os.path.join(
        os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
        "highbar-1.sock",
    )


def _parse_vec3(s: str) -> tuple[float, float, float]:
    parts = s.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"expected x,y,z — got {s!r}")
    return float(parts[0]), float(parts[1]), float(parts[2])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="HighBarV3 Python AI client")
    p.add_argument("--transport", choices=("uds", "tcp"), default="uds")
    p.add_argument("--uds-path", default=_default_uds_path())
    p.add_argument("--tcp-bind", default="127.0.0.1:50511")
    p.add_argument("--max-recv-mb", type=int, default=32)
    p.add_argument("--token-file", required=True)
    p.add_argument("--target-unit", type=int, required=True)
    p.add_argument("--move-to", type=_parse_vec3, required=True)
    p.add_argument("--token-wait-ms", type=int, default=5000)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    endpoint = channel.parse(args.transport, args.uds_path, args.tcp_bind)
    ch = channel.for_endpoint(endpoint, args.max_recv_mb)

    try:
        token = session.read_token_with_backoff(
            args.token_file, args.token_wait_ms
        )
        print(f"token loaded ({len(token)} chars)")

        hs = session.hello(
            ch,
            role=session.ClientRole.AI,
            client_id="hb-python-ai/0.1.0",
            token=token,
        )
        print(
            f"connected  session={hs.session_id}  schema={hs.schema_version} "
            f"frame={hs.current_frame}"
        )

        x, y, z = args.move_to
        b = commands.batch(
            target_unit=args.target_unit,
            batch_seq=1,
            orders=[commands.move_to(x, y, z)],
        )
        ack = commands.submit_one(ch, token, b)
        print(
            f"ack  last_batch_seq={ack.last_accepted_batch_seq} "
            f"accepted={ack.batches_accepted} "
            f"rejected_invalid={ack.batches_rejected_invalid} "
            f"rejected_full={ack.batches_rejected_full}"
        )
        return 0
    except grpc.RpcError as e:
        code = e.code() if hasattr(e, "code") else "?"
        print(f"rpc error: {code} — {e.details()}", file=sys.stderr)
        return 1
    except TimeoutError as e:
        print(f"token wait timed out: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
