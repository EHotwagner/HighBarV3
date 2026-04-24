// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — Hello handshake (T043, T045).
//
// Thin wrapper around the generated HighBarProxy client that
// performs the FR-022a strict-equality schema version check and
// surfaces the resulting session_id + static_map to the caller. AI
// role (token) support lands in US2 T063; this module handles the
// observer-role and token-authenticated paths uniformly.

namespace HighBar.Client

open System
open System.IO
open System.Threading
open System.Threading.Tasks
open Grpc.Core
open Grpc.Net.Client
open Highbar.V1

module Session =

    /// Schema version baked into the client. MUST match the
    /// compile-time constant on the plugin side
    /// (src/circuit/grpc/SchemaVersion.h). Any mismatch is a
    /// deployment error — loud, fast failure is the point.
    [<Literal>]
    let SchemaVersion = "1.0.0"

    type ClientRole = Observer | Ai

    /// Attempt to read the AI token file with exponential backoff
    /// (handles the plugin-startup race per spec Edge Case / data-
    /// model §7). Throws on timeout.
    let readTokenWithBackoff (path: string) (maxDelayMs: int) : Async<string> =
        async {
            let deadline = DateTime.UtcNow.AddMilliseconds(float maxDelayMs)
            let mutable delayMs = 25
            while not (File.Exists(path)) do
                if DateTime.UtcNow >= deadline then
                    failwithf "token file not present within %dms: %s" maxDelayMs path
                do! Async.Sleep(delayMs)
                delayMs <- min 1000 (delayMs * 2)
            return (File.ReadAllText(path).Trim())
        }

    /// Result of a successful handshake.
    type Handshake = {
        SessionId: string
        StaticMap: StaticMap
        CurrentFrame: uint32
        /// The ClientRole the handshake was opened with. Tokenless
        /// observers may still keep this to drive client-side RPC gating.
        Role: ClientRole
    }

    /// Open a Hello RPC. Returns Handshake on OK. FAILED_PRECONDITION
    /// from the server bubbles as an RpcException — callers should
    /// surface the status detail (contains both server and client
    /// schema versions) directly to the user.
    let hello (channel: GrpcChannel)
              (role: ClientRole)
              (clientId: string)
              (tokenOpt: string option)
              : Async<Handshake> =
        async {
            let client = HighBarProxy.HighBarProxyClient(channel)
            let req = HelloRequest(
                        SchemaVersion = SchemaVersion,
                        ClientId = clientId,
                        Role = (match role with
                                | Observer -> Highbar.V1.Role.Observer
                                | Ai -> Highbar.V1.Role.Ai))
            let metadata = Metadata()
            match tokenOpt with
            | Some t -> metadata.Add("x-highbar-ai-token", t)
            | None -> ()

            let call = client.HelloAsync(req, metadata)
            let! resp = call.ResponseAsync |> Async.AwaitTask

            // FR-022a defense in depth: the server already rejected a
            // mismatch with FAILED_PRECONDITION, but re-verify here so
            // tests that mock the server can't silently drift.
            if resp.SchemaVersion <> SchemaVersion then
                failwithf "schema mismatch: server=%s client=%s"
                          resp.SchemaVersion SchemaVersion

            return {
                SessionId = resp.SessionId
                StaticMap = resp.StaticMap
                CurrentFrame = resp.CurrentFrame
                Role = role
            }
        }

    let getCommandSchema (channel: GrpcChannel)
                         (metadata: Metadata)
                         (ct: CancellationToken)
                         : Async<CommandSchemaResponse> =
        async {
            let client = HighBarProxy.HighBarProxyClient(channel)
            let call = client.GetCommandSchemaAsync(
                           CommandSchemaRequest(),
                           metadata,
                           cancellationToken = ct)
            return! call.ResponseAsync |> Async.AwaitTask
        }

    let getUnitCapabilities (channel: GrpcChannel)
                            (metadata: Metadata)
                            (unitId: uint32)
                            (ct: CancellationToken)
                            : Async<UnitCapabilitiesResponse> =
        async {
            let client = HighBarProxy.HighBarProxyClient(channel)
            let req = UnitCapabilitiesRequest(UnitId = unitId)
            let call = client.GetUnitCapabilitiesAsync(
                           req,
                           metadata,
                           cancellationToken = ct)
            return! call.ResponseAsync |> Async.AwaitTask
        }
