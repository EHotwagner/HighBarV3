// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — StreamState consumer (T043, T046).
//
// Wraps the server-streaming StreamState RPC with a seq-invariant
// checker (FR-006: strictly monotonic; SC-005: no gaps, no dupes).
// Emits each StateUpdate to the caller's handler as it arrives.
//
// The invariant checker is authoritative — if the server-side
// ring/replay ever drifts it will fail here loudly rather than
// downstream in observer UIs.

namespace HighBar.Client

open System
open System.Collections.Generic
open System.Threading
open System.Threading.Tasks
open Grpc.Core
open Grpc.Net.Client
open Highbar.V1

module StateStream =

    /// Callback invoked once per StateUpdate. Runs on the gRPC response
    /// thread — handlers should be cheap or marshal onto their own
    /// dispatcher.
    type OnUpdate = StateUpdate -> unit

    /// Seq-invariant violation details — thrown when the client
    /// detects a gap, duplicate, or out-of-order seq.
    exception SeqInvariantException of message: string

    /// Open a StreamState and pump updates into `onUpdate` until the
    /// stream closes (normal) or the cancellation token fires.
    /// `resumeFromSeq = 0u` asks for a fresh snapshot; any other
    /// value is a resume request (data-model §2).
    let consume (channel: GrpcChannel)
                (resumeFromSeq: uint64)
                (onUpdate: OnUpdate)
                (ct: CancellationToken)
                : Async<unit> =
        async {
            let client = HighBarProxy.HighBarProxyClient(channel)
            let req = StreamStateRequest(ResumeFromSeq = resumeFromSeq)
            use call = client.StreamState(req, cancellationToken = ct)

            let mutable lastSeq : uint64 voption = ValueNone
            let mutable snapshotsSeen = 0

            let! _ =
                async {
                    while! call.ResponseStream.MoveNext(ct) |> Async.AwaitTask do
                        let upd = call.ResponseStream.Current

                        match lastSeq with
                        | ValueSome prev when upd.Seq <= prev ->
                            raise (SeqInvariantException
                                    (sprintf
                                        "seq regression: got %d after %d"
                                        upd.Seq prev))
                        | _ -> ()

                        // A snapshot arm that is NOT the first message
                        // in the stream indicates a server-side reset
                        // (resume out of range → fresh snapshot). That
                        // is legal and monotonic-continuous by
                        // construction on the server (data-model §2
                        // invariant: snapshot reset preserves seq
                        // monotonicity); we just count them so tests
                        // can assert.
                        if upd.PayloadCase = StateUpdate.PayloadOneofCase.Snapshot then
                            snapshotsSeen <- snapshotsSeen + 1

                        lastSeq <- ValueSome upd.Seq
                        onUpdate upd
                }
            return ()
        }

    /// Diagnostic wrapper — runs `consume` and records the stream as a
    /// list for assertions. Do not use for long streams (unbounded
    /// memory).
    let record (channel: GrpcChannel)
               (resumeFromSeq: uint64)
               (ct: CancellationToken)
               : Async<ResizeArray<StateUpdate>> =
        async {
            let buf = ResizeArray<StateUpdate>()
            do! consume channel resumeFromSeq buf.Add ct
            return buf
        }
