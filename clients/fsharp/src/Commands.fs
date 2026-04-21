// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — F# ergonomic wrapper over AICommand + SubmitCommands
// client-streaming helper (T062).
//
// The generated Highbar.V1.AICommand is a oneof over 97 command types;
// building the oneof by hand is verbose. This module exposes a small
// F# DU over the commonly-used unit-order commands and a batch helper
// that takes care of target_unit_id assignment, CommandOptions, and
// the client-stream ACK round trip (FR-010, FR-012a).
//
// Coverage mirrors CommandDispatch on the C++ side: move, patrol,
// fight, attack-area, stop, wait, build, repair, reclaim-unit,
// reclaim-area, resurrect-area, self-destruct, wanted-speed,
// fire-state, move-state. The generated AICommand.Builder is still
// accessible for clients that need the long tail.

namespace HighBar.Client

open System.Collections.Generic
open System.Threading
open System.Threading.Tasks
open Grpc.Core
open Grpc.Net.Client
open Highbar.V1

module Commands =

    /// Convenience type alias — the proto Vector3 is exposed to clients
    /// under Highbar.V1 but lifted here so call sites don't have to
    /// open the whole namespace.
    type Vec3 = Vector3

    let vec3 (x: float32) (y: float32) (z: float32) : Vec3 =
        Vector3(X = x, Y = y, Z = z)

    /// F# DU over the unit-order command set covered by the C++
    /// dispatcher. Add arms as the C++ side grows coverage — out-of-DU
    /// arms can still be issued by building AICommand directly.
    type Order =
        | MoveTo      of Vec3
        | PatrolTo    of Vec3
        | FightTo     of Vec3
        | AttackArea  of pos: Vec3 * radius: float32
        | Stop
        | Wait
        | Build       of defId: int32 * pos: Vec3 * facing: int32
        | Repair      of repairUnitId: int32
        | ReclaimUnit of reclaimUnitId: int32
        | ReclaimArea of pos: Vec3 * radius: float32
        | ResurrectArea of pos: Vec3 * radius: float32
        | SelfDestruct
        | WantedSpeed of float32
        | FireState   of int32
        | MoveState   of int32

    /// CommandOptions bitfield per common.proto. Use when the batch
    /// should queue (SHIFT) instead of interrupt-current.
    [<Struct>]
    type Opts =
        { Shift: bool
          Ctrl: bool
          Alt: bool }
        static member None = { Shift = false; Ctrl = false; Alt = false }
        static member Queued = { Shift = true; Ctrl = false; Alt = false }

    let private optsToBitfield (o: Opts) : uint32 =
        let mutable b = 0u
        if o.Shift then b <- b ||| 1u
        if o.Ctrl then b <- b ||| 2u
        if o.Alt then b <- b ||| 4u
        b

    /// Build an AICommand from an `Order` + the target unit id + options.
    let toProto (unitId: int32) (opts: Opts) (order: Order) : AICommand =
        let cmd = AICommand()
        let bits = optsToBitfield opts
        match order with
        | MoveTo pos ->
            cmd.MoveUnit <- MoveUnitCommand(
                UnitId = unitId, Options = bits, ToPosition = pos)
        | PatrolTo pos ->
            cmd.Patrol <- PatrolCommand(
                UnitId = unitId, Options = bits, ToPosition = pos)
        | FightTo pos ->
            cmd.Fight <- FightCommand(
                UnitId = unitId, Options = bits, ToPosition = pos)
        | AttackArea (pos, radius) ->
            cmd.AttackArea <- AttackAreaCommand(
                UnitId = unitId, Options = bits,
                AttackPosition = pos, Radius = radius)
        | Stop ->
            cmd.Stop <- StopCommand(UnitId = unitId, Options = bits)
        | Wait ->
            cmd.Wait <- WaitCommand(UnitId = unitId, Options = bits)
        | Build (defId, pos, facing) ->
            cmd.BuildUnit <- BuildUnitCommand(
                UnitId = unitId, Options = bits,
                ToBuildUnitDefId = defId,
                BuildPosition = pos, Facing = facing)
        | Repair repairId ->
            cmd.Repair <- RepairCommand(
                UnitId = unitId, Options = bits, RepairUnitId = repairId)
        | ReclaimUnit reclaimId ->
            cmd.ReclaimUnit <- ReclaimUnitCommand(
                UnitId = unitId, Options = bits, ReclaimUnitId = reclaimId)
        | ReclaimArea (pos, radius) ->
            cmd.ReclaimArea <- ReclaimAreaCommand(
                UnitId = unitId, Options = bits,
                Position = pos, Radius = radius)
        | ResurrectArea (pos, radius) ->
            cmd.ResurrectInArea <- ResurrectInAreaCommand(
                UnitId = unitId, Options = bits,
                Position = pos, Radius = radius)
        | SelfDestruct ->
            cmd.SelfDestruct <- SelfDestructCommand(
                UnitId = unitId, Options = bits)
        | WantedSpeed v ->
            cmd.SetWantedMaxSpeed <- SetWantedMaxSpeedCommand(
                UnitId = unitId, Options = bits, WantedMaxSpeed = v)
        | FireState s ->
            cmd.SetFireState <- SetFireStateCommand(
                UnitId = unitId, Options = bits, FireState = s)
        | MoveState s ->
            cmd.SetMoveState <- SetMoveStateCommand(
                UnitId = unitId, Options = bits, MoveState = s)
        cmd

    /// Build a CommandBatch carrying orders for a single target.
    let batch (targetUnitId: uint32)
              (batchSeq: uint64)
              (opts: Opts)
              (orders: Order list)
              : CommandBatch =
        let b = CommandBatch(
                    BatchSeq = batchSeq,
                    TargetUnitId = targetUnitId)
        for ord in orders do
            b.Commands.Add(toProto (int32 targetUnitId) opts ord)
        b

    /// SubmitCommands session wrapper. Opens the client-streaming RPC,
    /// writes each batch, and surfaces the CommandAck on completion.
    /// The AI token MUST have been added to `metadata` by the caller —
    /// Session.readTokenWithBackoff + manual Metadata.Add is the
    /// idiomatic path (see samples/AiClient).
    type SubmitSession(channel: GrpcChannel, metadata: Metadata, ct: CancellationToken) =
        let client = HighBarProxy.HighBarProxyClient(channel)
        let call = client.SubmitCommands(metadata, cancellationToken = ct)

        /// Send a CommandBatch. Throws RpcException on queue overflow
        /// (RESOURCE_EXHAUSTED) or validation failure (INVALID_ARGUMENT)
        /// — the server closes the stream on either.
        member _.SendAsync(batch: CommandBatch) : Task =
            call.RequestStream.WriteAsync(batch)

        /// Close the client-side of the stream and await the final
        /// CommandAck.
        member _.CompleteAsync() : Task<CommandAck> =
            task {
                do! call.RequestStream.CompleteAsync()
                return! call.ResponseAsync
            }

        interface System.IDisposable with
            member _.Dispose() = call.Dispose()

    /// Convenience: open a submit session, write a single batch, close,
    /// and return the ACK. Appropriate for fire-and-forget patterns
    /// (samples, tests). For long-lived streaming use SubmitSession.
    let submitOne (channel: GrpcChannel)
                  (metadata: Metadata)
                  (b: CommandBatch)
                  (ct: CancellationToken)
                  : Async<CommandAck> =
        async {
            use session = new SubmitSession(channel, metadata, ct)
            do! session.SendAsync(b) |> Async.AwaitTask
            let! ack = session.CompleteAsync() |> Async.AwaitTask
            return ack
        }
