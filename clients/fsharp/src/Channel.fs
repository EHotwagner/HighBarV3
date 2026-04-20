// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — gRPC channel construction (T043, T044).
//
// Builds Grpc.Net.Client GrpcChannel instances for the two transports
// the plugin supports:
//   * UDS  — SocketsHttpHandler + ConnectCallback to an
//            UnixDomainSocketEndPoint. Standard pattern on .NET 8.
//   * TCP  — plain http://host:port (loopback only per US4).
//
// The URI scheme is always http:// (plaintext). FR-013/14 delegate
// confidentiality to the filesystem (UDS mode 0600 on the token) and
// the loopback-only TCP bind; there is no TLS on the in-process
// trust boundary.

namespace HighBar.Client

open System
open System.IO
open System.Net.Http
open System.Net.Sockets
open System.Threading
open System.Threading.Tasks
open Grpc.Net.Client

module Channel =

    /// Transport discriminator — matches the `transport` field in
    /// data/config/grpc.json.
    type Endpoint =
        | Uds of path: string
        | Tcp of hostPort: string

    /// Build a GrpcChannel for the given endpoint. `maxRecvMb` bumps
    /// the channel's max receive size so late-game snapshots (>4MB)
    /// don't trip the default limit (plan §Technical Context).
    let forEndpoint (endpoint: Endpoint) (maxRecvMb: int) : GrpcChannel =
        let opts = GrpcChannelOptions()
        opts.MaxReceiveMessageSize <- Nullable<int>(maxRecvMb * 1024 * 1024)

        match endpoint with
        | Uds path ->
            let handler = new SocketsHttpHandler()
            handler.ConnectCallback <-
                Func<SocketsHttpConnectionContext, CancellationToken, ValueTask<Stream>>(
                    fun _ ct ->
                        ValueTask<Stream>(
                            task {
                                let socket = new Socket(AddressFamily.Unix,
                                                         SocketType.Stream,
                                                         ProtocolType.Unspecified)
                                try
                                    let ep = UnixDomainSocketEndPoint(path)
                                    do! socket.ConnectAsync(ep, ct).AsTask()
                                    return new NetworkStream(socket, ownsSocket = true) :> Stream
                                with
                                | ex ->
                                    socket.Dispose()
                                    return raise ex
                            }))
            opts.HttpHandler <- handler
            // The scheme+host only serve to identify the channel in
            // logs; the ConnectCallback overrides all networking.
            GrpcChannel.ForAddress("http://localhost", opts)

        | Tcp hostPort ->
            GrpcChannel.ForAddress("http://" + hostPort, opts)

    /// Construct an Endpoint from a config-style pair. Matches the
    /// shape data/config/grpc.json emits, so higher layers can stay
    /// transport-agnostic. UDS is default when the caller's string is
    /// a filesystem path; TCP otherwise.
    let parse (transport: string) (udsPath: string) (tcpBind: string) : Endpoint =
        match transport.ToLowerInvariant() with
        | "uds" -> Uds udsPath
        | "tcp" -> Tcp tcpBind
        | other -> invalidArg "transport" $"unknown transport '{other}' (expected uds|tcp)"
