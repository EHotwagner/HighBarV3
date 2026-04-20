// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — F# observer sample (T047).
//
// Matches the flow in quickstart.md §5. Connects to the gateway over
// UDS (default) or TCP, performs the Hello handshake, then pumps the
// StreamState until Ctrl-C.
//
// Build + run:
//   cd clients/fsharp/samples/Observer
//   dotnet run --   \
//     --transport uds \
//     --uds-path $XDG_RUNTIME_DIR/highbar-1.sock

module HighBar.Samples.Observer.Program

open System
open System.Threading
open HighBar.Client
open Highbar.V1

type Args = {
    Transport: string
    UdsPath: string
    TcpBind: string
    MaxRecvMb: int
    ResumeFromSeq: uint64
}

let defaults = {
    Transport = "uds"
    UdsPath = sprintf "%s/highbar-1.sock"
                    (Environment.GetEnvironmentVariable "XDG_RUNTIME_DIR"
                     |> Option.ofObj |> Option.defaultValue "/tmp")
    TcpBind = "127.0.0.1:50511"
    MaxRecvMb = 32
    ResumeFromSeq = 0UL
}

let rec parseArgs (args: string list) (acc: Args) : Args =
    match args with
    | [] -> acc
    | "--transport" :: v :: rest -> parseArgs rest { acc with Transport = v }
    | "--uds-path"  :: v :: rest -> parseArgs rest { acc with UdsPath = v }
    | "--tcp-bind"  :: v :: rest -> parseArgs rest { acc with TcpBind = v }
    | "--max-recv-mb" :: v :: rest ->
        parseArgs rest { acc with MaxRecvMb = Int32.Parse v }
    | "--resume-from-seq" :: v :: rest ->
        parseArgs rest { acc with ResumeFromSeq = UInt64.Parse v }
    | unknown :: _ ->
        eprintfn "unknown arg: %s" unknown
        eprintfn "usage: Observer [--transport uds|tcp] [--uds-path PATH] [--tcp-bind HOST:PORT] [--max-recv-mb N] [--resume-from-seq N]"
        exit 2

[<EntryPoint>]
let main argv =
    let args = parseArgs (Array.toList argv) defaults
    let endpoint = Channel.parse args.Transport args.UdsPath args.TcpBind
    let channel = Channel.forEndpoint endpoint args.MaxRecvMb

    let cts = new CancellationTokenSource()
    Console.CancelKeyPress.Add(fun e ->
        e.Cancel <- true
        cts.Cancel())

    try
        let hs =
            Session.hello channel Session.Observer "hb-fsharp-observer/0.1.0" None
            |> Async.RunSynchronously

        printfn "connected  session=%s  schema=%s  frame=%d"
                hs.SessionId Session.SchemaVersion hs.CurrentFrame
        printfn "static_map cells=%dx%d metal_spots=%d"
                hs.StaticMap.WidthCells
                hs.StaticMap.HeightCells
                hs.StaticMap.MetalSpots.Count

        let onUpdate (upd: StateUpdate) =
            match upd.PayloadCase with
            | StateUpdate.PayloadOneofCase.Snapshot ->
                printfn "seq=%d frame=%d SNAPSHOT own=%d enemies=%d"
                    upd.Seq upd.Frame
                    upd.Snapshot.OwnUnits.Count
                    upd.Snapshot.VisibleEnemies.Count
            | StateUpdate.PayloadOneofCase.Delta ->
                printfn "seq=%d frame=%d DELTA events=%d"
                    upd.Seq upd.Frame upd.Delta.Events.Count
            | StateUpdate.PayloadOneofCase.Keepalive ->
                printfn "seq=%d frame=%d KEEPALIVE" upd.Seq upd.Frame
            | _ -> printfn "seq=%d unknown payload" upd.Seq

        StateStream.consume channel args.ResumeFromSeq onUpdate cts.Token
        |> Async.RunSynchronously

        0
    with
    | :? OperationCanceledException ->
        printfn "canceled."
        0
    | ex ->
        eprintfn "error: %s" ex.Message
        1
