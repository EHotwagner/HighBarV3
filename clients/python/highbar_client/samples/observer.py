# SPDX-License-Identifier: GPL-2.0-only
"""Python observer sample (T088).

Matches quickstart.md §7 and the F# observer (samples/Observer/). Runs
until Ctrl-C or the server closes the stream.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys

import grpc

from .. import SCHEMA_VERSION, channel, session, state_stream
from ..highbar.v1 import state_pb2  # type: ignore


def _default_uds_path() -> str:
    return os.path.join(
        os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
        "highbar-1.sock",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="HighBarV3 Python observer")
    p.add_argument("--transport", choices=("uds", "tcp"), default="uds")
    p.add_argument("--uds-path", default=_default_uds_path())
    p.add_argument("--tcp-bind", default="127.0.0.1:50511")
    p.add_argument("--max-recv-mb", type=int, default=32)
    p.add_argument("--resume-from-seq", type=int, default=0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    endpoint = channel.parse(args.transport, args.uds_path, args.tcp_bind)
    ch = channel.for_endpoint(endpoint, args.max_recv_mb)

    # Graceful Ctrl-C — close the channel so grpcio sends CANCELLED.
    def _on_sigint(_sig, _frm):
        try:
            ch.close()
        except Exception:  # noqa: BLE001 — best effort during shutdown
            pass

    signal.signal(signal.SIGINT, _on_sigint)

    try:
        hs = session.hello(
            ch, role=session.ClientRole.OBSERVER,
            client_id="hb-python-observer/0.1.0",
        )
        print(
            f"connected  session={hs.session_id}  schema={SCHEMA_VERSION} "
            f"frame={hs.current_frame}"
        )
        print(
            f"static_map cells={hs.static_map.width_cells}x"
            f"{hs.static_map.height_cells} "
            f"metal_spots={len(hs.static_map.metal_spots)}"
        )

        for upd in state_stream.consume(ch, resume_from_seq=args.resume_from_seq):
            case = upd.WhichOneof("payload")
            if case == "snapshot":
                print(
                    f"seq={upd.seq} frame={upd.frame} SNAPSHOT "
                    f"own={len(upd.snapshot.own_units)} "
                    f"enemies={len(upd.snapshot.visible_enemies)}"
                )
            elif case == "delta":
                print(
                    f"seq={upd.seq} frame={upd.frame} DELTA "
                    f"events={len(upd.delta.events)}"
                )
            elif case == "keepalive":
                print(f"seq={upd.seq} frame={upd.frame} KEEPALIVE")
            else:
                print(f"seq={upd.seq} unknown payload")
        return 0
    except grpc.RpcError as e:
        code = e.code() if hasattr(e, "code") else "?"
        print(f"rpc error: {code} — {e.details()}", file=sys.stderr)
        return 1
    except state_stream.SeqInvariantError as e:
        print(f"seq invariant violated: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
