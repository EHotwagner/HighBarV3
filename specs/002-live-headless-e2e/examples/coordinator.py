#!/usr/bin/env python3
"""HighBarCoordinator — client-mode relay.

Hosts TWO services on the same gRPC server:

  1. HighBarCoordinator (the plugin dials in via this)
     - Heartbeat       : unary
     - PushState       : plugin streams StateUpdates here
     - OpenCommandChannel: coord streams CommandBatches to plugin

  2. HighBarProxy (external observers / AI-role clients dial in via this)
     - Hello           : unary handshake
     - StreamState     : observer gets relayed StateUpdates from the
                         plugin's PushState feed (fan-out)
     - SubmitCommands  : AI-role client streams CommandBatches;
                         coordinator forwards them to the plugin via
                         the OpenCommandChannel stream
     - Others          : UNIMPLEMENTED (future phases)

This is the "flip" — server-mode HighBarProxy now lives in the
coordinator instead of the plugin. The existing F# / Python clients
written against HighBarProxy work unchanged; they just connect to the
coordinator endpoint instead of the plugin's UDS.
"""
import sys
import os
import time
import queue
import threading
import argparse

sys.path.insert(0, "/tmp/hb-run/pyproto")

import grpc
from concurrent import futures
from highbar import coordinator_pb2, coordinator_pb2_grpc
from highbar import commands_pb2, service_pb2, service_pb2_grpc
from highbar import state_pb2


class Relay:
    """Thread-safe hub connecting plugin feeds to external clients."""

    def __init__(self):
        # State broadcast: PushState pushes here, StreamState subscribers read.
        # Per-subscriber Queue, unbounded (best-effort; real impl would bound).
        self._state_subs_lock = threading.Lock()
        self._state_subs = []  # list[queue.Queue[state_pb2.StateUpdate]]
        # Command forward: SubmitCommands pushes here, OpenCommandChannel pulls.
        # One central queue for now (future: per-plugin-session).
        self.cmd_forward = queue.Queue()
        self.state_updates_received = 0
        self.max_seq_seen = 0
        self.commands_relayed = 0

    def add_state_subscriber(self):
        q = queue.Queue(maxsize=8192)
        with self._state_subs_lock:
            self._state_subs.append(q)
        return q

    def remove_state_subscriber(self, q):
        with self._state_subs_lock:
            try:
                self._state_subs.remove(q)
            except ValueError:
                pass

    def publish_state(self, update):
        self.state_updates_received += 1
        if update.seq > self.max_seq_seen:
            self.max_seq_seen = update.seq
        with self._state_subs_lock:
            for q in self._state_subs:
                try:
                    q.put_nowait(update)
                except queue.Full:
                    pass  # slow subscriber; drop

    def forward_command(self, batch):
        self.cmd_forward.put(batch)
        self.commands_relayed += 1


# ----------------------------------------------------------------------
# HighBarCoordinator service (plugin-facing)
# ----------------------------------------------------------------------

class CoordSvc(coordinator_pb2_grpc.HighBarCoordinatorServicer):
    def __init__(self, coord_id, relay):
        self.coord_id = coord_id
        self.relay = relay
        self.heartbeats = 0

    def Heartbeat(self, request, context):
        self.heartbeats += 1
        if self.heartbeats % 50 == 1:
            print(f"[hb={self.heartbeats:04d}] plugin={request.plugin_id} "
                  f"frame={request.frame}", flush=True)
        return coordinator_pb2.HeartbeatResponse(
            coordinator_id=self.coord_id,
            echoed_frame=request.frame,
            schema_version="1.0.0",
        )

    def PushState(self, request_iterator, context):
        peer = context.peer()
        print(f"[push] plugin stream opened peer={peer}", flush=True)
        for update in request_iterator:
            self.relay.publish_state(update)
        print(f"[push] plugin stream closed peer={peer} "
              f"total_seen={self.relay.state_updates_received}", flush=True)
        return coordinator_pb2.PushAck(
            messages_received=self.relay.state_updates_received,
            max_seq_seen=self.relay.max_seq_seen,
            coordinator_id=self.coord_id,
        )

    def OpenCommandChannel(self, request, context):
        print(f"[cmd-ch] plugin={request.plugin_id} subscribed "
              f"peer={context.peer()}", flush=True)
        # Serve forwarded commands from the central queue until the
        # plugin disconnects.
        try:
            while context.is_active():
                try:
                    batch = self.relay.cmd_forward.get(timeout=0.5)
                    print(f"[cmd-ch] forwarding batch "
                          f"seq={batch.batch_seq} "
                          f"ncmds={len(batch.commands)}", flush=True)
                    yield batch
                except queue.Empty:
                    continue
        except grpc.RpcError:
            pass
        print(f"[cmd-ch] plugin={request.plugin_id} disconnected",
              flush=True)


# ----------------------------------------------------------------------
# HighBarProxy service (external-client-facing; the "flip")
# ----------------------------------------------------------------------

class ProxySvc(service_pb2_grpc.HighBarProxyServicer):
    def __init__(self, coord_id, relay):
        self.coord_id = coord_id
        self.relay = relay
        self.session_seq = 0

    def _new_session_id(self):
        self.session_seq += 1
        return f"{self.coord_id}-sess-{self.session_seq}"

    def Hello(self, request, context):
        print(f"[proxy] Hello from {context.peer()} "
              f"schema={request.schema_version}", flush=True)
        if request.schema_version != "1.0.0":
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            context.set_details(
                f"schema mismatch: server=1.0.0 client={request.schema_version}")
            return service_pb2.HelloResponse()
        return service_pb2.HelloResponse(
            schema_version="1.0.0",
            session_id=self._new_session_id(),
            current_frame=0,
        )

    def StreamState(self, request, context):
        print(f"[proxy] StreamState subscriber from {context.peer()} "
              f"resume_from_seq={request.resume_from_seq}", flush=True)
        q = self.relay.add_state_subscriber()
        try:
            while context.is_active():
                try:
                    update = q.get(timeout=0.5)
                    yield update
                except queue.Empty:
                    continue
        finally:
            self.relay.remove_state_subscriber(q)
            print(f"[proxy] StreamState subscriber from {context.peer()} "
                  f"disconnected", flush=True)

    def SubmitCommands(self, request_iterator, context):
        n = 0
        for batch in request_iterator:
            self.relay.forward_command(batch)
            n += 1
        print(f"[proxy] SubmitCommands from {context.peer()}: "
              f"received {n} batches, forwarded", flush=True)
        return service_pb2.CommandAck(
            last_accepted_batch_seq=n,
            batches_accepted=n,
            batches_rejected_invalid=0,
            batches_rejected_full=0,
        )


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", required=True)
    p.add_argument("--id", default=f"coord-{os.getpid()}")
    args = p.parse_args()

    if args.endpoint.startswith("unix:"):
        path = args.endpoint[5:]
        try: os.unlink(path)
        except FileNotFoundError: pass

    relay = Relay()
    coord_svc = CoordSvc(args.id, relay)
    proxy_svc = ProxySvc(args.id, relay)

    srv = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    coordinator_pb2_grpc.add_HighBarCoordinatorServicer_to_server(coord_svc, srv)
    service_pb2_grpc.add_HighBarProxyServicer_to_server(proxy_svc, srv)
    srv.add_insecure_port(args.endpoint)
    srv.start()
    print(f"coordinator id={args.id} "
          f"(HighBarCoordinator + HighBarProxy) listening on {args.endpoint}",
          flush=True)
    try:
        srv.wait_for_termination()
    except KeyboardInterrupt:
        srv.stop(0)


if __name__ == "__main__":
    main()
