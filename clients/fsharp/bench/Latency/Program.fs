// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — F# latency microbench (T065).
//
// Measures p50/p99/p999 round-trip for unary Hello against a running
// plugin. Gates against Constitution V: p99 ≤ 500µs on UDS (T072's
// CI wrapper checks the exit code). The spec's preferred signal
// (UnitDamaged engine event → F# OnEvent) requires an engine-side
// InvokeCallback bridge which lands in a follow-up; Hello is the
// next-best unary round-trip available on the Phase 4 surface and
// exercises the same CQ worker hot path.
//
// Exits:
//   0  — ran a sample, budget met (or --gate disabled)
//   1  — sample ran but budget exceeded (--gate enabled)
//   77 — skip (plugin not running / channel unreachable), mimicking
//        autotools skip semantics for CI wrappers.
//
// Build + run:
//   cd clients/fsharp/bench/Latency
//   dotnet run -c Release -- \
//     --transport uds --uds-path $XDG_RUNTIME_DIR/highbar-1.sock \
//     --samples 5000 --gate-p99-us 500

module HighBar.Bench.Latency.Program

open System
open System.Diagnostics
open System.Threading
open HighBar.Client
open Highbar.V1

type Args = {
    Transport: string
    UdsPath: string
    TcpBind: string
    MaxRecvMb: int
    Samples: int
    Warmup: int
    GateP99Us: int option
}

let defaults = {
    Transport = "uds"
    UdsPath = sprintf "%s/highbar-1.sock"
                (Environment.GetEnvironmentVariable "XDG_RUNTIME_DIR"
                 |> Option.ofObj |> Option.defaultValue "/tmp")
    TcpBind = "127.0.0.1:50511"
    MaxRecvMb = 32
    Samples = 5000
    Warmup = 500
    GateP99Us = None
}

let rec parseArgs (args: string list) (acc: Args) : Args =
    match args with
    | [] -> acc
    | "--transport" :: v :: rest -> parseArgs rest { acc with Transport = v }
    | "--uds-path"  :: v :: rest -> parseArgs rest { acc with UdsPath = v }
    | "--tcp-bind"  :: v :: rest -> parseArgs rest { acc with TcpBind = v }
    | "--max-recv-mb" :: v :: rest ->
        parseArgs rest { acc with MaxRecvMb = Int32.Parse v }
    | "--samples" :: v :: rest -> parseArgs rest { acc with Samples = Int32.Parse v }
    | "--warmup"  :: v :: rest -> parseArgs rest { acc with Warmup = Int32.Parse v }
    | "--gate-p99-us" :: v :: rest ->
        parseArgs rest { acc with GateP99Us = Some (Int32.Parse v) }
    | unknown :: _ ->
        eprintfn "unknown arg: %s" unknown
        exit 2

let percentile (sorted: int64 array) (p: float) : int64 =
    if sorted.Length = 0 then 0L
    else
        let idx = min (sorted.Length - 1) (int (ceil (p * float sorted.Length)) - 1)
        sorted.[max 0 idx]

[<EntryPoint>]
let main argv =
    let args = parseArgs (Array.toList argv) defaults
    let endpoint = Channel.parse args.Transport args.UdsPath args.TcpBind
    let channel = Channel.forEndpoint endpoint args.MaxRecvMb

    // Probe connectivity: a single Hello. If it throws, skip.
    try
        let _ =
            Session.hello channel Session.Observer "hb-fsharp-bench/0.1.0" None
            |> Async.RunSynchronously
        ()
    with ex ->
        eprintfn "skip: plugin unreachable (%s)" ex.Message
        exit 77

    // Warmup — drain JIT and ThreadPool noise.
    for _ in 1 .. args.Warmup do
        Session.hello channel Session.Observer "hb-fsharp-bench/0.1.0" None
        |> Async.RunSynchronously
        |> ignore

    let samples = Array.zeroCreate<int64> args.Samples
    let sw = Stopwatch()
    for i in 0 .. args.Samples - 1 do
        sw.Restart()
        Session.hello channel Session.Observer "hb-fsharp-bench/0.1.0" None
        |> Async.RunSynchronously
        |> ignore
        sw.Stop()
        let us = sw.Elapsed.Ticks * 1_000_000L / TimeSpan.TicksPerSecond
        samples.[i] <- us

    Array.sortInPlace samples
    let p50  = percentile samples 0.50
    let p99  = percentile samples 0.99
    let p999 = percentile samples 0.999

    printfn "samples=%d  transport=%s" args.Samples args.Transport
    printfn "p50=%dus  p99=%dus  p999=%dus  max=%dus"
            p50 p99 p999 samples.[samples.Length - 1]

    match args.GateP99Us with
    | Some gate when int p99 > gate ->
        eprintfn "FAIL: p99=%dus exceeds gate %dus" p99 gate
        1
    | _ ->
        0
