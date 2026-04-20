// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — F# AI-role sample (T064).
//
// Matches quickstart.md §6. Opens a channel, reads the AI token from
// $writeDir/highbar.token (with exponential backoff for the startup
// race), performs the AI-role Hello, then sends one CommandBatch
// containing a MoveTo order for the --target-unit unit. Prints the
// returned CommandAck and exits.
//
// Build + run:
//   cd clients/fsharp/samples/AiClient
//   dotnet run -- \
//     --transport uds \
//     --uds-path $XDG_RUNTIME_DIR/highbar-1.sock \
//     --token-file $WRITE_DIR/highbar.token \
//     --target-unit 42 \
//     --move-to 1024,0,1024

module HighBar.Samples.AiClient.Program

open System
open System.Threading
open HighBar.Client
open Highbar.V1

type Args = {
    Transport: string
    UdsPath: string
    TcpBind: string
    MaxRecvMb: int
    TokenFile: string
    TargetUnit: int
    MoveTo: (float32 * float32 * float32) option
}

let defaults = {
    Transport = "uds"
    UdsPath = sprintf "%s/highbar-1.sock"
                    (Environment.GetEnvironmentVariable "XDG_RUNTIME_DIR"
                     |> Option.ofObj |> Option.defaultValue "/tmp")
    TcpBind = "127.0.0.1:50511"
    MaxRecvMb = 32
    TokenFile =
        let home = Environment.GetEnvironmentVariable "HOME" |> Option.ofObj |> Option.defaultValue ""
        sprintf "%s/highbar.token" home
    TargetUnit = 0
    MoveTo = None
}

let parseVec (s: string) : float32 * float32 * float32 =
    let parts = s.Split(',')
    if parts.Length <> 3 then
        eprintfn "--move-to expects x,y,z (got %s)" s
        exit 2
    (Single.Parse parts.[0], Single.Parse parts.[1], Single.Parse parts.[2])

let rec parseArgs (args: string list) (acc: Args) : Args =
    match args with
    | [] -> acc
    | "--transport" :: v :: rest -> parseArgs rest { acc with Transport = v }
    | "--uds-path"  :: v :: rest -> parseArgs rest { acc with UdsPath = v }
    | "--tcp-bind"  :: v :: rest -> parseArgs rest { acc with TcpBind = v }
    | "--max-recv-mb" :: v :: rest ->
        parseArgs rest { acc with MaxRecvMb = Int32.Parse v }
    | "--token-file" :: v :: rest -> parseArgs rest { acc with TokenFile = v }
    | "--target-unit" :: v :: rest ->
        parseArgs rest { acc with TargetUnit = Int32.Parse v }
    | "--move-to" :: v :: rest ->
        parseArgs rest { acc with MoveTo = Some (parseVec v) }
    | unknown :: _ ->
        eprintfn "unknown arg: %s" unknown
        eprintfn "usage: AiClient --target-unit N [--move-to x,y,z] [--token-file PATH] [--transport uds|tcp] [--uds-path PATH] [--tcp-bind HOST:PORT]"
        exit 2

[<EntryPoint>]
let main argv =
    let args = parseArgs (Array.toList argv) defaults
    if args.TargetUnit <= 0 then
        eprintfn "--target-unit is required"
        exit 2

    let endpoint = Channel.parse args.Transport args.UdsPath args.TcpBind
    let channel = Channel.forEndpoint endpoint args.MaxRecvMb

    let cts = new CancellationTokenSource()
    Console.CancelKeyPress.Add(fun e ->
        e.Cancel <- true
        cts.Cancel())

    try
        // AI-role Hello: reads token with exponential backoff, then
        // attaches x-highbar-ai-token.
        let hs, token =
            Session.helloAi channel "hb-fsharp-ai/0.1.0" args.TokenFile 5000
            |> Async.RunSynchronously

        printfn "connected  session=%s  frame=%d" hs.SessionId hs.CurrentFrame

        let cmd =
            match args.MoveTo with
            | Some (x, y, z) -> Commands.MoveTo (x, y, z)
            | None -> Commands.Stop
        let batch = Commands.batch 1UL args.TargetUnit cmd

        let ack =
            Commands.submit channel token [ batch ] cts.Token
            |> Async.RunSynchronously

        printfn "ack  accepted=%d rejected_invalid=%d rejected_full=%d last_seq=%d"
                ack.BatchesAccepted ack.BatchesRejectedInvalid
                ack.BatchesRejectedFull ack.LastAcceptedBatchSeq
        0
    with
    | :? OperationCanceledException ->
        printfn "canceled."
        0
    | ex ->
        eprintfn "error: %s" ex.Message
        1
