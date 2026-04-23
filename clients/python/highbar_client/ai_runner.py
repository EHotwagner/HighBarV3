# SPDX-License-Identifier: GPL-2.0-only
"""Run Python AI policy plugins through the unchanged HighBar proxy AI."""

from __future__ import annotations

import argparse
import os
import sys

import grpc

from . import channel, session, state_stream
from .ai_plugins import (
    AIPluginContext,
    client_id_for_plugin,
    load_ai_plugin,
    parse_plugin_config,
)


def _default_uds_path() -> str:
    return os.path.join(
        os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
        "highbar-1.sock",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HighBarV3 Python AI plugin runner")
    parser.add_argument("--transport", choices=("uds", "tcp"), default="uds")
    parser.add_argument("--uds-path", default=_default_uds_path())
    parser.add_argument("--tcp-bind", default="127.0.0.1:50511")
    parser.add_argument("--max-recv-mb", type=int, default=32)
    parser.add_argument("--token-file", required=True)
    parser.add_argument(
        "--ai-plugin",
        default="idle",
        help="built-in plugin name or module:attribute factory",
    )
    parser.add_argument(
        "--plugin-config",
        default="",
        help="JSON object passed to the plugin factory",
    )
    parser.add_argument(
        "--name-addon",
        default=os.environ.get("HIGHBAR_AI_NAME_ADDON", ""),
        help="safe suffix added to the ROLE_AI client id for distinguishing policies",
    )
    parser.add_argument("--token-wait-ms", type=int, default=5000)
    parser.add_argument("--resume-from-seq", type=int, default=0)
    parser.add_argument(
        "--max-updates",
        type=int,
        default=0,
        help="stop after this many state updates; 0 means run until interrupted",
    )
    parser.add_argument(
        "--stream-timeout-seconds",
        type=float,
        default=None,
        help="optional StreamState deadline",
    )
    parser.add_argument(
        "--submit-timeout-seconds",
        type=float,
        default=5.0,
        help="timeout for each command batch submission",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plugin = load_ai_plugin(
            args.ai_plugin,
            config=parse_plugin_config(args.plugin_config),
        )
        client_id = client_id_for_plugin(plugin, name_addon=args.name_addon)
        endpoint = channel.parse(args.transport, args.uds_path, args.tcp_bind)
        ch = channel.for_endpoint(endpoint, args.max_recv_mb)
        token = session.read_token_with_backoff(args.token_file, args.token_wait_ms)
        handshake = session.hello(
            ch,
            role=session.ClientRole.AI,
            client_id=client_id,
            token=token,
        )
        context = AIPluginContext(
            channel=ch,
            token=token,
            handshake=handshake,
            client_id=client_id,
            name_addon=args.name_addon,
        )
        print(
            f"ai-runner: connected client_id={client_id} "
            f"session={handshake.session_id} plugin={plugin.name}/{plugin.version}",
            flush=True,
        )
        plugin.on_start(context)
        updates_seen = 0
        batches_submitted = 0
        try:
            for update in state_stream.consume(
                ch,
                resume_from_seq=args.resume_from_seq,
                max_wait_seconds=args.stream_timeout_seconds,
            ):
                updates_seen += 1
                for batch in plugin.on_state(context, update):
                    ack = context.submit(
                        batch,
                        timeout=args.submit_timeout_seconds,
                    )
                    batches_submitted += ack.batches_accepted
                if args.max_updates > 0 and updates_seen >= args.max_updates:
                    break
        finally:
            plugin.on_stop(context)
        print(
            f"ai-runner: stopped updates={updates_seen} "
            f"batches_submitted={batches_submitted}",
            flush=True,
        )
        return 0
    except grpc.RpcError as exc:
        code = exc.code() if hasattr(exc, "code") else "?"
        print(f"ai-runner: rpc error: {code} - {exc.details()}", file=sys.stderr)
        return 1
    except (TimeoutError, ValueError, TypeError, ImportError, AttributeError) as exc:
        print(f"ai-runner: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())

