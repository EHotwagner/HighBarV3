#!/usr/bin/env python3
"""Relay HighBar admin autohost commands to the engine autohost socket."""

from __future__ import annotations

import argparse
import socket
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    engine_addr: tuple[str, int] | None = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", args.port))
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"{time.time():.6f} relay listening port={args.port}\n")
            log.flush()
            while True:
                payload, addr = sock.recvfrom(65535)
                if payload.startswith(b"/"):
                    if engine_addr is None:
                        log.write(
                            f"{time.time():.6f} drop command no-engine-yet "
                            f"from={addr} payload={payload!r}\n"
                        )
                    else:
                        sock.sendto(payload, engine_addr)
                        log.write(
                            f"{time.time():.6f} relay command from={addr} "
                            f"to={engine_addr} payload={payload!r}\n"
                        )
                    log.flush()
                    continue

                engine_addr = addr
                log.write(
                    f"{time.time():.6f} engine event from={addr} "
                    f"bytes={len(payload)} first={payload[:1]!r}\n"
                )
                log.flush()


if __name__ == "__main__":
    raise SystemExit(main())
