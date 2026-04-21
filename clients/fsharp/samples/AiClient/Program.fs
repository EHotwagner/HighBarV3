// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — F# AI-role sample (T064).
//
// Matches the flow in quickstart.md §6. Reads the AI token with
// exponential backoff (handles the plugin-startup race), performs the
// Hello handshake as role AI, then submits a MoveTo batch for the
// supplied target unit. Exits after the CommandAck returns.
//
// Build + run:
//   cd clients/fsharp/samples/AiClient
//   dotnet run -- \
//     --transport uds \
//     --uds-path $XDG_RUNTIME_DIR/highbar-1.sock \
//     --token-file $XDG_DATA_HOME/HighBar/highbar.token \
//     --target-unit 42 \
//     --move-to 1024,0,1024

module HighBar.Samples.AiClient.Program

open System
open System.Threading
open Grpc.Core
open HighBar.Client
open Highbar.V1

type Args = {
    Transport: string
    UdsPath: string
    TcpBind: string
    MaxRecvMb: int
    TokenFile: string
    TargetUnit: uint32
    MoveTo: (float32 * float32 * float32) option
    TokenWaitMs: int
}

let defaults = {
    Transport = "uds"
    UdsPath = sprintf "%s/highbar-1.sock"
                    (Environment.GetEnvironmentVariable "XDG_RUNTIME_DIR"
                     |> Option.ofObj |> Option.defaultValue "/tmp")
    TcpBind = "127.0.0.1:50511"
    MaxRecvMb = 32
    TokenFile = "highbar.token"
    TargetUnit = 0u
    MoveTo = None
    TokenWaitMs = 5000
}

let parseVec3 (s: string) : (float32 * float32 * float32) =
    let parts = s.Split ','
    if parts.Length <> 3 then
        failwithf "expected x,y,z — got %s" s
    (Single.Parse parts.[0], Single.Parse parts.[1], Single.Parse parts.[2])

let rec parseArgs (args: string list) (acc: Args) : Args =
    match args with
    | [] -> acc
    | "--transport" :: v :: rest -> parseArgs rest { acc with Transport = v }
    | "--uds-path"  :: v :: rest -> parseArgs rest { acc with UdsPath = v }
    | "--tcp-bind"  :: v :: rest -> parseArgs rest { acc with TcpBind = v }
    | "--max-recv-mb" :: v :: rest ->
        parseArgs rest { acc with MaxRecvMb = Int32.Parse v }
    | "--token-file" :: v :: rest ->
        parseArgs rest { acc with TokenFile = v }
    | "--target-unit" :: v :: rest ->
        parseArgs rest { acc with TargetUnit = UInt32.Parse v }
    | "--move-to" :: v :: rest ->
        parseArgs rest { acc with MoveTo = Some (parseVec3 v) }
    | "--token-wait-ms" :: v :: rest ->
        parseArgs rest { acc with TokenWaitMs = Int32.Parse v }
    | unknown :: _ ->
        eprintfn "unknown arg: %s" unknown
        eprintfn "usage: AiClient [--transport uds|tcp] [--uds-path PATH] \
                  [--tcp-bind HOST:PORT] [--max-recv-mb N] --token-file PATH \
                  --target-unit N --move-to X,Y,Z [--token-wait-ms MS]"
        exit 2

[<EntryPoint>]
let main argv =
    let args = parseArgs (Array.toList argv) defaults
    if args.TargetUnit = 0u then
        eprintfn "missing --target-unit"
        exit 2
    if args.MoveTo.IsNone then
        eprintfn "missing --move-to"
        exit 2

    let endpoint = Channel.parse args.Transport args.UdsPath args.TcpBind
    let channel = Channel.forEndpoint endpoint args.MaxRecvMb

    use cts = new CancellationTokenSource()
    Console.CancelKeyPress.Add(fun e ->
        e.Cancel <- true
        cts.Cancel())

    try
        // Read the AI token with exponential backoff — handles the
        // plugin-startup race where the sample launches before the
        // token file lands.
        let token =
            Session.readTokenWithBackoff args.TokenFile args.TokenWaitMs
            |> Async.RunSynchronously
        printfn "token loaded (%d chars)" token.Length

        // AI-role handshake. The interceptor on the server bypasses
        // Hello for the token check — we still attach it so subsequent
        // SubmitCommands on the same channel re-uses the metadata.
        let hs =
            Session.hello channel Session.Ai "hb-fsharp-ai/0.1.0"
                          (Some token)
            |> Async.RunSynchronously
        printfn "connected  session=%s  schema=%s  frame=%d"
                hs.SessionId Session.SchemaVersion hs.CurrentFrame

        // Build a single-command batch for the requested MoveTo.
        let (x, y, z) = args.MoveTo.Value
        let batch =
            Commands.batch
                args.TargetUnit
                1UL  // batch_seq
                Commands.Opts.None
                [ Commands.MoveTo (Commands.vec3 x y z) ]

        let metadata = Metadata()
        metadata.Add("x-highbar-ai-token", token)

        let ack =
            Commands.submitOne channel metadata batch cts.Token
            |> Async.RunSynchronously
        printfn "ack  last_batch_seq=%d accepted=%d rejected_invalid=%d rejected_full=%d"
                ack.LastAcceptedBatchSeq
                ack.BatchesAccepted
                ack.BatchesRejectedInvalid
                ack.BatchesRejectedFull
        0
    with
    | :? OperationCanceledException ->
        printfn "canceled."
        0
    | :? RpcException as ex ->
        eprintfn "rpc error: %s — %s" (string ex.StatusCode) ex.Status.Detail
        1
    | ex ->
        eprintfn "error: %s" ex.Message
        1
