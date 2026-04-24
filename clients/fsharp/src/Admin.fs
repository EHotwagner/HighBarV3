// SPDX-License-Identifier: GPL-2.0-only

namespace HighBar.Client

open System.Threading
open Grpc.Core
open Grpc.Net.Client
open Highbar.V1

module Admin =

    let unitTransferAction actionSeq clientActionId unitId fromTeamId toTeamId preserveOrders =
        let action = AdminAction()
        action.ActionSeq <- actionSeq
        action.ClientActionId <- clientActionId
        action.ConflictPolicy <- AdminConflictPolicy.AdminConflictRejectIfControlled
        action.UnitTransfer <- UnitTransferAction(
                                   UnitId = unitId,
                                   FromTeamId = fromTeamId,
                                   ToTeamId = toTeamId,
                                   PreserveOrders = preserveOrders)
        action

    let getCapabilities (channel: GrpcChannel)
                        (metadata: Metadata)
                        (ct: CancellationToken)
                        : Async<AdminCapabilitiesResponse> =
        async {
            let client = HighBarAdmin.HighBarAdminClient(channel)
            let call = client.GetAdminCapabilitiesAsync(
                           AdminCapabilitiesRequest(),
                           metadata,
                           cancellationToken = ct)
            return! call.ResponseAsync |> Async.AwaitTask
        }

    let validateAction (channel: GrpcChannel)
                       (metadata: Metadata)
                       (action: AdminAction)
                       (ct: CancellationToken)
                       : Async<AdminActionResult> =
        async {
            let client = HighBarAdmin.HighBarAdminClient(channel)
            let call = client.ValidateAdminActionAsync(
                           action,
                           metadata,
                           cancellationToken = ct)
            return! call.ResponseAsync |> Async.AwaitTask
        }

    let executeAction (channel: GrpcChannel)
                      (metadata: Metadata)
                      (action: AdminAction)
                      (ct: CancellationToken)
                      : Async<AdminActionResult> =
        async {
            let client = HighBarAdmin.HighBarAdminClient(channel)
            let call = client.ExecuteAdminActionAsync(
                           action,
                           metadata,
                           cancellationToken = ct)
            return! call.ResponseAsync |> Async.AwaitTask
        }
