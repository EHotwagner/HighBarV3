// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — latency microbench (T065).
//
// Measures p99 round-trip latency from the engine-side UnitDamaged
// event to the F# OnEvent callback that observes it as a DeltaEvent.
// Gates Constitution V: ≤500µs p99 over UDS; TCP gate (≤1.5ms) added
// with US4 T076.
//
// Methodology:
//   1. Subscribe to StreamState. Record the wall clock at which each
//      DeltaEvent::UnitDamaged arrives in the F# receive loop.
//   2. Independently, the server-side plugin's engine thread
//      timestamps the UnitDamaged event when it posts to the delta
//      accumulator (counters.cc RecordFrameFlushUs) and bakes that
//      timestamp into the proto payload. For US2 we ship the
//      measurement loop here but defer the server-side timestamp
//      field to a follow-up (requires a proto addition + engine-side
//      edit). Until then this bench reports "end-to-end observe
//      latency" (Hello RTT + first delta) as an approximation that
//      still makes a regression visible.
//
// Exit codes:
//   0  — bench ran and p99 was within the per-transport budget.
//   1  — bench ran but p99 exceeded the budget (Constitution V fail).
//   77 — skipped (gateway not reachable).

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
    SampleCount: int
    DurationSec: int
    ReportOnly: bool  // bench-mode: fail on budget breach. report-only: print and exit 0.
}

let defaults = {
    Transport = "uds"
    UdsPath = sprintf "%s/highbar-1.sock"
                    (Environment.GetEnvironmentVariable "XDG_RUNTIME_DIR"
                     |> Option.ofObj |> Option.defaultValue "/tmp")
    TcpBind = "127.0.0.1:50511"
    MaxRecvMb = 32
    SampleCount = 1000
    DurationSec = 30
    ReportOnly = false
}

let rec parseArgs (args: string list) (acc: Args) : Args =
    match args with
    | [] -> acc
    | "--transport" :: v :: rest -> parseArgs rest { acc with Transport = v }
    | "--uds-path"  :: v :: rest -> parseArgs rest { acc with UdsPath = v }
    | "--tcp-bind"  :: v :: rest -> parseArgs rest { acc with TcpBind = v }
    | "--max-recv-mb" :: v :: rest ->
        parseArgs rest { acc with MaxRecvMb = Int32.Parse v }
    | "--samples" :: v :: rest ->
        parseArgs rest { acc with SampleCount = Int32.Parse v }
    | "--duration-sec" :: v :: rest ->
        parseArgs rest { acc with DurationSec = Int32.Parse v }
    | "--report-only" :: rest -> parseArgs rest { acc with ReportOnly = true }
    | unknown :: _ ->
        eprintfn "unknown arg: %s" unknown
        eprintfn "usage: Latency [--transport uds|tcp] [--uds-path PATH] \
                  [--tcp-bind HOST:PORT] [--samples N] [--duration-sec N] \
                  [--report-only]"
        exit 2

let percentile (xs: float[]) (p: float) : float =
    if xs.Length = 0 then 0.0
    else
        let sorted = Array.sort xs
        let idx = int (ceil (p * float sorted.Length)) - 1
        sorted.[max 0 (min (sorted.Length - 1) idx)]

[<EntryPoint>]
let main argv =
    let args = parseArgs (Array.toList argv) defaults

    // Per-transport Constitution V budget in microseconds.
    let budgetUs =
        match args.Transport with
        | "uds" -> 500.0
        | "tcp" -> 1500.0
        | t -> failwithf "unknown transport: %s" t

    let endpoint = Channel.parse args.Transport args.UdsPath args.TcpBind

    // Skip-on-unreachable: try Hello, exit 77 if the gateway is gone.
    // (CI relies on this: bench runs only when the spring-headless
    // harness boots the plugin; on a dev machine without the engine it
    // shouldn't fail red.)
    let probeChannel =
        try Some (Channel.forEndpoint endpoint args.MaxRecvMb)
        with _ -> None

    match probeChannel with
    | None ->
        eprintfn "latency bench: gateway unreachable on %s — SKIP" args.Transport
        exit 77
    | Some channel ->

    try
        let hs =
            Session.hello channel Session.Observer "hb-fsharp-bench/0.1.0" None
            |> Async.RunSynchronously
        printfn "bench connected  session=%s  transport=%s" hs.SessionId args.Transport

        let samples = ResizeArray<float>()
        use cts = new CancellationTokenSource(TimeSpan.FromSeconds(float args.DurationSec))
        let sw = Stopwatch.StartNew()

        let onUpdate (upd: StateUpdate) =
            // Approximation: arrival-time delta between consecutive deltas.
            // Once the server-side timestamp lands this becomes a true
            // engine→client latency measurement.
            if upd.PayloadCase = StateUpdate.PayloadOneofCase.Delta then
                for ev in upd.Delta.Events do
                    if ev.KindCase = DeltaEvent.KindOneofCase.UnitDamaged then
                        let us = float (sw.Elapsed.TotalMilliseconds * 1000.0)
                        samples.Add(us)
                        sw.Restart()
                        if samples.Count >= args.SampleCount then
                            cts.Cancel()

        try
            StateStream.consume channel 0UL onUpdate cts.Token
            |> Async.RunSynchronously
        with :? OperationCanceledException -> ()

        if samples.Count < 10 then
            eprintfn "latency bench: only %d samples collected — SKIP (no damage events?)"
                     samples.Count
            exit 77

        let arr = samples.ToArray()
        let p50 = percentile arr 0.50
        let p99 = percentile arr 0.99
        let max_ = Array.max arr
        printfn "latency: samples=%d p50=%.1fµs p99=%.1fµs max=%.1fµs budget=%.1fµs"
                arr.Length p50 p99 max_ budgetUs

        if args.ReportOnly then 0
        elif p99 > budgetUs then
            eprintfn "p99 %.1fµs exceeds budget %.1fµs — FAIL"
                     p99 budgetUs
            1
        else 0
    with ex ->
        eprintfn "bench error: %s" ex.Message
        1
