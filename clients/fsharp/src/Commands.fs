// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — F# SubmitCommands wrapper (T062).
//
// Provides an F#-ergonomic DU over the 97-arm AICommand oneof (the
// common unit commands expand into DU cases; the rest are reachable
// via Command.Raw passing the generated protobuf AICommand directly).
//
// `submit` opens the SubmitCommands client-stream, sends N batches,
// and returns the final CommandAck. Validation / RESOURCE_EXHAUSTED
// bubble as RpcException — callers should surface the server's status
// detail to the user.

namespace HighBar.Client

open System
open System.Threading
open System.Threading.Tasks
open Grpc.Core
open Grpc.Net.Client
open Highbar.V1

module Commands =

    /// Thin F# DU over the common AICommand arms. For arms not listed
    /// here — drawing, chat, groups, pathfinding, Lua, cheats, figures,
    /// Attack (needs enemy id), Guard, Capture, Load/Unload, etc. —
    /// pass a pre-built `AICommand` via `Raw`.
    type Command =
        | MoveTo of x: float32 * y: float32 * z: float32
        | Stop
        | PatrolTo of x: float32 * y: float32 * z: float32
        | FightTo of x: float32 * y: float32 * z: float32
        | AttackArea of x: float32 * y: float32 * z: float32 * radius: float32
        | Build of toBuildDefId: int * x: float32 * y: float32 * z: float32 * facing: int
        | Repair of targetUnitId: int
        | ReclaimUnit of targetUnitId: int
        | ReclaimArea of x: float32 * y: float32 * z: float32 * radius: float32
        | SelfDestruct
        | Wait
        | SetWantedMaxSpeed of speed: float32
        | SetFireState of state: int
        | SetMoveState of state: int
        | Raw of AICommand

    let private vec3 (x: float32) (y: float32) (z: float32) : Vector3 =
        let v = Vector3()
        v.X <- x
        v.Y <- y
        v.Z <- z
        v

    /// Translate an F# DU into a protobuf AICommand. `unitId` is passed
    /// into every unit command's `unit_id` field for V2 compatibility;
    /// the engine-side dispatcher uses `CommandBatch.target_unit_id` as
    /// authoritative but V2-shaped commands carry it too.
    let toProto (unitId: int) (c: Command) : AICommand =
        match c with
        | Raw raw -> raw
        | MoveTo (x, y, z) ->
            let cmd = AICommand()
            let m = MoveUnitCommand()
            m.UnitId <- unitId
            m.Timeout <- Int32.MaxValue
            m.ToPosition <- vec3 x y z
            cmd.MoveUnit <- m
            cmd
        | Stop ->
            let cmd = AICommand()
            let s = StopCommand()
            s.UnitId <- unitId
            s.Timeout <- Int32.MaxValue
            cmd.Stop <- s
            cmd
        | PatrolTo (x, y, z) ->
            let cmd = AICommand()
            let p = PatrolCommand()
            p.UnitId <- unitId
            p.Timeout <- Int32.MaxValue
            p.ToPosition <- vec3 x y z
            cmd.Patrol <- p
            cmd
        | FightTo (x, y, z) ->
            let cmd = AICommand()
            let f = FightCommand()
            f.UnitId <- unitId
            f.Timeout <- Int32.MaxValue
            f.ToPosition <- vec3 x y z
            cmd.Fight <- f
            cmd
        | AttackArea (x, y, z, r) ->
            let cmd = AICommand()
            let a = AttackAreaCommand()
            a.UnitId <- unitId
            a.Timeout <- Int32.MaxValue
            a.AttackPosition <- vec3 x y z
            a.Radius <- r
            cmd.AttackArea <- a
            cmd
        | Build (defId, x, y, z, facing) ->
            let cmd = AICommand()
            let b = BuildUnitCommand()
            b.UnitId <- unitId
            b.Timeout <- Int32.MaxValue
            b.ToBuildUnitDefId <- defId
            b.BuildPosition <- vec3 x y z
            b.Facing <- facing
            cmd.BuildUnit <- b
            cmd
        | Repair tgt ->
            let cmd = AICommand()
            let r = RepairCommand()
            r.UnitId <- unitId
            r.Timeout <- Int32.MaxValue
            r.RepairUnitId <- tgt
            cmd.Repair <- r
            cmd
        | ReclaimUnit tgt ->
            let cmd = AICommand()
            let r = ReclaimUnitCommand()
            r.UnitId <- unitId
            r.Timeout <- Int32.MaxValue
            r.ReclaimUnitId <- tgt
            cmd.ReclaimUnit <- r
            cmd
        | ReclaimArea (x, y, z, rad) ->
            let cmd = AICommand()
            let r = ReclaimAreaCommand()
            r.UnitId <- unitId
            r.Timeout <- Int32.MaxValue
            r.Position <- vec3 x y z
            r.Radius <- rad
            cmd.ReclaimArea <- r
            cmd
        | SelfDestruct ->
            let cmd = AICommand()
            let s = SelfDestructCommand()
            s.UnitId <- unitId
            s.Timeout <- Int32.MaxValue
            cmd.SelfDestruct <- s
            cmd
        | Wait ->
            let cmd = AICommand()
            let w = WaitCommand()
            w.UnitId <- unitId
            w.Timeout <- Int32.MaxValue
            cmd.Wait <- w
            cmd
        | SetWantedMaxSpeed spd ->
            let cmd = AICommand()
            let s = SetWantedMaxSpeedCommand()
            s.UnitId <- unitId
            s.Timeout <- Int32.MaxValue
            s.WantedMaxSpeed <- spd
            cmd.SetWantedMaxSpeed <- s
            cmd
        | SetFireState state ->
            let cmd = AICommand()
            let s = SetFireStateCommand()
            s.UnitId <- unitId
            s.Timeout <- Int32.MaxValue
            s.FireState <- state
            cmd.SetFireState <- s
            cmd
        | SetMoveState state ->
            let cmd = AICommand()
            let s = SetMoveStateCommand()
            s.UnitId <- unitId
            s.Timeout <- Int32.MaxValue
            s.MoveState <- state
            cmd.SetMoveState <- s
            cmd

    /// Build a single-command CommandBatch for one target unit.
    let batch (batchSeq: uint64) (unitId: int) (c: Command) : CommandBatch =
        let b = CommandBatch()
        b.BatchSeq <- batchSeq
        b.TargetUnitId <- uint32 unitId
        b.Commands.Add(toProto unitId c)
        b

    /// Open SubmitCommands with the AI-token metadata, stream the
    /// provided batches sequentially, then close the client-half and
    /// await the final CommandAck.
    let submit (channel: GrpcChannel)
               (token: string)
               (batches: CommandBatch seq)
               (ct: CancellationToken)
               : Async<CommandAck> =
        async {
            let client = HighBarProxy.HighBarProxyClient(channel)
            let metadata = Metadata()
            metadata.Add("x-highbar-ai-token", token)
            use call = client.SubmitCommands(metadata, cancellationToken = ct)

            for b in batches do
                do! call.RequestStream.WriteAsync(b) |> Async.AwaitTask
            do! call.RequestStream.CompleteAsync() |> Async.AwaitTask

            let! ack = call.ResponseAsync |> Async.AwaitTask
            return ack
        }
