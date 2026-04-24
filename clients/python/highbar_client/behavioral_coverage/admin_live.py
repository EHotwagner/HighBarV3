# SPDX-License-Identifier: GPL-2.0-only
"""Live admin behavioral evidence collection."""

from __future__ import annotations

import os
import socket
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import grpc

from .. import admin, channel, session
from ..highbar import service_pb2, service_pb2_grpc, state_pb2
from .admin_actions import (
    AdminBehaviorScenario,
    AdminCaller,
    AdminObservation,
    all_scenarios,
    pause_action,
    resource_grant_action,
    speed_action,
    unit_spawn_action,
    unit_transfer_action,
)
from .admin_observations import ObservedMatchState
from .admin_suite import evidence_record, missing_evidence_record


class LiveAdminEvidenceError(RuntimeError):
    """Raised when live evidence cannot be collected."""


class StateCollector:
    def __init__(self, grpc_channel: grpc.Channel):
        self._channel = grpc_channel
        self._stub = service_pb2_grpc.HighBarProxyStub(grpc_channel)
        self._cv = threading.Condition()
        self._snapshots: list[tuple[int, state_pb2.StateSnapshot]] = []
        self._updates: list[state_pb2.StateUpdate] = []
        self._error: BaseException | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="admin-state-stream", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._channel.close()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        try:
            for update in self._stub.StreamState(service_pb2.StreamStateRequest()):
                with self._cv:
                    self._updates.append(update)
                    if update.WhichOneof("payload") == "snapshot":
                        self._snapshots.append((int(update.seq), update.snapshot))
                    self._cv.notify_all()
                if self._stop.is_set():
                    break
        except grpc.RpcError as exc:
            if not self._stop.is_set():
                with self._cv:
                    self._error = exc
                    self._cv.notify_all()
        except BaseException as exc:  # noqa: BLE001 - preserve background error for caller
            with self._cv:
                self._error = exc
                self._cv.notify_all()

    def latest_seq(self) -> int:
        with self._cv:
            return int(self._updates[-1].seq) if self._updates else 0

    def latest_frame(self) -> int:
        with self._cv:
            return int(self._updates[-1].frame) if self._updates else 0

    def request_snapshot(self, token: str, *, timeout: float) -> int:
        response = self._stub.RequestSnapshot(
            service_pb2.RequestSnapshotRequest(),
            metadata=[(session.TOKEN_HEADER, token)],
            timeout=timeout,
        )
        return int(response.scheduled_frame)

    def wait_for_snapshot_after(self, min_seq: int, *, timeout: float) -> tuple[int, state_pb2.StateSnapshot]:
        deadline = time.monotonic() + timeout
        with self._cv:
            while True:
                for seq, snapshot in reversed(self._snapshots):
                    if seq > min_seq:
                        return seq, snapshot
                if self._error is not None:
                    raise LiveAdminEvidenceError(f"state stream failed: {self._error}") from self._error
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LiveAdminEvidenceError("timed out waiting for state snapshot")
                self._cv.wait(min(remaining, 0.1))

    def wait_for_seq_after(self, min_seq: int, *, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        with self._cv:
            while True:
                if self._updates and int(self._updates[-1].seq) > min_seq:
                    return
                if self._error is not None:
                    raise LiveAdminEvidenceError(f"state stream failed: {self._error}") from self._error
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                self._cv.wait(min(remaining, 0.1))

    def updates_between(self, start_seq: int, end_seq: int) -> list[state_pb2.StateUpdate]:
        with self._cv:
            return [update for update in self._updates if start_seq < int(update.seq) <= end_seq]


def wait_for_live_paths(endpoint: str, token_file: str, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    sock_path = endpoint.removeprefix("unix:")
    while time.monotonic() < deadline:
        socket_ready = not endpoint.startswith("unix:") or socket_exists(sock_path)
        token_ready = Path(token_file).is_file()
        if socket_ready and token_ready:
            return
        time.sleep(0.05)
    raise LiveAdminEvidenceError(f"live endpoint or token missing: endpoint={endpoint} token={token_file}")


def socket_exists(path: str) -> bool:
    return bool(path) and os.path.exists(path) and stat_is_socket(path)


def stat_is_socket(path: str) -> bool:
    try:
        return socket.S_ISSOCK(os.stat(path).st_mode)  # type: ignore[attr-defined]
    except AttributeError:
        import stat

        return stat.S_ISSOCK(os.stat(path).st_mode)
    except OSError:
        return False


def channel_for_endpoint(endpoint: str) -> grpc.Channel:
    if endpoint.startswith("unix:"):
        return channel.for_endpoint(channel.Endpoint.uds(endpoint.removeprefix("unix:")))
    return channel.for_endpoint(channel.Endpoint.tcp(endpoint))


def state_from_snapshot(
    snapshot: state_pb2.StateSnapshot,
    *,
    updates: list[state_pb2.StateUpdate] | None = None,
    previous: ObservedMatchState | None = None,
) -> ObservedMatchState:
    units: dict[int, dict[str, Any]] = {}
    for unit in snapshot.own_units:
        units[int(unit.unit_id)] = {
            "team_id": int(unit.team_id),
            "unit_def_id": int(unit.def_id),
            "position": (float(unit.position.x), float(unit.position.y), float(unit.position.z)),
        }
    for unit in snapshot.visible_enemies:
        units[int(unit.unit_id)] = {
            "team_id": int(unit.team_id),
            "unit_def_id": int(unit.def_id),
            "position": (float(unit.position.x), float(unit.position.y), float(unit.position.z)),
        }
    economy = snapshot.economy
    resources = {
        (0, 0): float(economy.metal),
        (0, 1): float(economy.energy),
    }
    for update in updates or ():
        if update.WhichOneof("payload") != "delta":
            continue
        for event in update.delta.events:
            kind = event.WhichOneof("kind")
            if kind == "unit_given":
                prior = units.get(int(event.unit_given.unit_id))
                if prior is None and previous is not None:
                    prior = previous.units.get(int(event.unit_given.unit_id))
                units[int(event.unit_given.unit_id)] = {
                    "team_id": int(event.unit_given.new_team_id),
                    "unit_def_id": (prior or {}).get("unit_def_id", 0),
                    "position": (prior or {}).get("position", (0.0, 0.0, 0.0)),
                }
            elif kind == "economy_tick":
                economy = event.economy_tick
                resources[(0, 0)] = float(economy.metal)
                resources[(0, 1)] = float(economy.energy)
    return ObservedMatchState(
        frame=int(snapshot.frame_number),
        resources=resources,
        units=units,
    )


def scenario_for_live(
    scenario: AdminBehaviorScenario,
    snapshot: state_pb2.StateSnapshot,
) -> AdminBehaviorScenario:
    own_units = list(snapshot.own_units)
    anchor = own_units[0] if own_units else None
    own_team = int(anchor.team_id) if anchor is not None else 0
    enemy_team = 0 if own_team != 0 else 1
    if scenario.scenario_id == "grant_resource" and anchor is not None:
        amount = max(float(scenario.action.resource_grant.amount), 5000.0)
        return replace(
            scenario,
            action=resource_grant_action(
                int(scenario.action.action_seq),
                own_team,
                int(scenario.action.resource_grant.resource_id),
                amount,
            ),
            expected_observation=AdminObservation("resource_grant", "resource_delta", 1.0, tolerance=0.01),
        )
    if scenario.scenario_id == "spawn_enemy_unit" and anchor is not None:
        position = (
            float(anchor.position.x) + 256.0,
            float(anchor.position.y),
            float(anchor.position.z),
        )
        return replace(
            scenario,
            action=unit_spawn_action(
                int(scenario.action.action_seq),
                own_team,
                int(anchor.def_id),
                position,
            ),
        )
    if scenario.scenario_id == "transfer_unit" and anchor is not None:
        transfer_unit = own_units[-1]
        return replace(
            scenario,
            action=unit_transfer_action(
                int(scenario.action.action_seq),
                int(transfer_unit.unit_id),
                int(transfer_unit.team_id),
                enemy_team,
            ),
        )
    return scenario


def execute_live_suite(
    *,
    endpoint: str,
    token_file: str,
    timeout_seconds: float,
    log_location: str = "",
) -> tuple[list[Any], dict[str, Any]]:
    wait_for_live_paths(endpoint, token_file, timeout=timeout_seconds)
    token = session.read_token_with_backoff(token_file, max_delay_ms=int(timeout_seconds * 1000))
    state_channel = channel_for_endpoint(endpoint)
    admin_channel = channel_for_endpoint(endpoint)
    wait_for_channel_ready(state_channel, timeout=timeout_seconds)
    wait_for_channel_ready(admin_channel, timeout=timeout_seconds)
    collector = StateCollector(state_channel)
    collector.start()
    capabilities: dict[str, Any] = {}
    records = []
    stage = "connect"
    try:
        stage = "hello"
        session.hello(state_channel, session.ClientRole.OBSERVER, "admin-behavior-observer")
        stage = "initial_snapshot"
        _, initial = collector.wait_for_snapshot_after(-1, timeout=timeout_seconds)
        stage = "own_unit"
        wait_for_own_unit(collector, token, initial, timeout_seconds)
        capabilities = {
            "supported_actions": ["pause", "global_speed", "resource_grant", "unit_spawn", "unit_transfer"],
            "valid_team_ids": [],
            "valid_resource_ids": [0, 1],
            "valid_unit_def_ids": [],
            "min_speed": 0.1,
            "max_speed": 10.0,
            "headless_fixture": True,
            "unit_transfer_enabled": True,
            "capability_source": "behavioral_action_execution",
        }
        scenarios = list(all_scenarios())
        scenario_order = {
            "resume_match": 10,
            "set_speed_fast": 20,
            "grant_resource": 30,
            "spawn_enemy_unit": 40,
            "reject_unauthorized": 50,
            "reject_invalid_speed": 60,
            "reject_invalid_resource": 70,
            "reject_invalid_spawn": 80,
            "reject_invalid_transfer": 90,
            "reject_lease_conflict": 100,
            "transfer_unit": 110,
            "pause_match": 120,
        }
        scenarios = sorted(scenarios, key=lambda item: scenario_order.get(item.scenario_id, 1000))
        for scenario in scenarios:
            scenario = scenario_for_live(scenario, latest_snapshot(collector))
            stage = f"scenario:{scenario.scenario_id}"
            records.append(run_live_scenario(admin_channel, collector, token, scenario, timeout_seconds, log_location))
    except grpc.RpcError as exc:
        raise LiveAdminEvidenceError(f"admin live RPC failed during {stage}: {exc.code().name}: {exc.details()}") from exc
    except LiveAdminEvidenceError as exc:
        raise LiveAdminEvidenceError(f"{exc} during {stage}") from exc
    finally:
        try:
            admin.execute_action(
                admin_channel,
                token,
                pause_action(9901, False),
                timeout=1.0,
                admin_role="operator",
                client_id="admin-suite-cleanup",
            )
            admin.execute_action(
                admin_channel,
                token,
                speed_action(9902, 1.0),
                timeout=1.0,
                admin_role="operator",
                client_id="admin-suite-cleanup",
            )
        except Exception:
            pass
        collector.stop()
        admin_channel.close()
    return records, capabilities


def wait_for_channel_ready(grpc_channel: grpc.Channel, *, timeout: float) -> None:
    try:
        grpc.channel_ready_future(grpc_channel).result(timeout=timeout)
    except grpc.FutureTimeoutError as exc:
        raise LiveAdminEvidenceError("timed out waiting for gRPC endpoint readiness") from exc


def snapshot_now(
    collector: StateCollector,
    token: str,
    timeout_seconds: float,
) -> tuple[int, state_pb2.StateSnapshot]:
    min_seq = collector.latest_seq()
    collector.request_snapshot(token, timeout=timeout_seconds)
    return collector.wait_for_snapshot_after(min_seq, timeout=timeout_seconds)


def latest_snapshot(collector: StateCollector) -> state_pb2.StateSnapshot:
    with collector._cv:  # noqa: SLF001 - small internal helper
        if not collector._snapshots:
            raise LiveAdminEvidenceError("no live snapshot available")
        return collector._snapshots[-1][1]


def capture_state(
    collector: StateCollector,
    *,
    previous: ObservedMatchState | None = None,
) -> tuple[int, ObservedMatchState]:
    with collector._cv:  # noqa: SLF001 - small internal helper
        if not collector._snapshots:
            raise LiveAdminEvidenceError("no live snapshot available")
        snapshot_seq, snapshot = collector._snapshots[-1]
        latest_seq = int(collector._updates[-1].seq) if collector._updates else snapshot_seq
        latest_frame = int(collector._updates[-1].frame) if collector._updates else int(snapshot.frame_number)
    updates = collector.updates_between(snapshot_seq, latest_seq)
    state = state_from_snapshot(snapshot, updates=updates, previous=previous)
    return latest_seq, replace(state, frame=max(state.frame, latest_frame))


def wait_for_own_unit(
    collector: StateCollector,
    token: str,
    initial: state_pb2.StateSnapshot,
    timeout_seconds: float,
) -> None:
    if initial.own_units:
        return
    deadline = time.monotonic() + timeout_seconds
    min_seq = -1
    while time.monotonic() < deadline:
        try:
            seq, snapshot = collector.wait_for_snapshot_after(min_seq, timeout=min(2.0, timeout_seconds))
        except LiveAdminEvidenceError as exc:
            if "timed out waiting for state snapshot" not in str(exc):
                raise
            continue
        min_seq = seq
        if snapshot.own_units:
            return
    raise LiveAdminEvidenceError("live fixture did not expose an own unit for admin tests")


def run_live_scenario(
    grpc_channel: grpc.Channel,
    collector: StateCollector,
    token: str,
    scenario: AdminBehaviorScenario,
    timeout_seconds: float,
    log_location: str,
):
    before_seq, before = capture_state(collector)
    log_offset = log_size(log_location)

    if scenario.scenario_id == "reject_lease_conflict":
        admin.execute_action(
            grpc_channel,
            token,
            pause_action(8002, False),
            timeout=timeout_seconds,
            admin_role="operator",
            client_id="admin-suite",
        )

    caller: AdminCaller = scenario.caller
    result = admin.execute_action(
        grpc_channel,
        token,
        scenario.action,
        timeout=timeout_seconds,
        admin_role=caller.role_name,
        client_id=caller.client_id,
    )
    if scenario.scenario_id == "set_speed_fast":
        observed_speed = wait_for_engine_speed(
            log_location,
            expected=float(scenario.action.global_speed.speed),
            start_offset=log_offset,
            timeout=min(timeout_seconds, 3.0),
        )
        return evidence_record(
            scenario,
            result_status=int(result.status),
            before=before,
            after=replace(before, speed=observed_speed),
            evidence_source="engine_log",
            log_location=log_location,
        )
    if scenario.scenario_id in {"grant_resource", "spawn_enemy_unit", "transfer_unit"}:
        try:
            collector.request_snapshot(token, timeout=min(timeout_seconds, 2.0))
        except Exception:
            pass
    time.sleep(0.15)
    if scenario.scenario_id == "pause_match":
        time.sleep(0.15)
        before = replace(before, frame=collector.latest_frame())
        time.sleep(0.25)
        after = replace(before, frame=collector.latest_frame())
        record = evidence_record(
            scenario,
            result_status=int(result.status),
            before=before,
            after=after,
            evidence_source="state_stream",
            log_location=log_location,
        )
        admin.execute_action(
            grpc_channel,
            token,
            pause_action(8100 + int(scenario.action.action_seq), False),
            timeout=timeout_seconds,
            admin_role="operator",
            client_id="admin-suite",
        )
        collector.wait_for_seq_after(collector.latest_seq(), timeout=min(timeout_seconds, 2.0))
        time.sleep(0.2)
        return record

    collector.wait_for_seq_after(before_seq, timeout=min(timeout_seconds, 2.0))
    after_seq, after = capture_state(collector, previous=before)
    if scenario.scenario_id == "transfer_unit":
        transfer = scenario.action.unit_transfer
        units = dict(after.units)
        for update in collector.updates_between(before_seq, after_seq):
            if update.WhichOneof("payload") != "delta":
                continue
            for event in update.delta.events:
                if event.WhichOneof("kind") != "unit_given":
                    continue
                if int(event.unit_given.unit_id) != int(transfer.unit_id):
                    continue
                prior = before.units.get(int(transfer.unit_id), {})
                units[int(transfer.unit_id)] = {
                    "team_id": int(event.unit_given.new_team_id),
                    "unit_def_id": prior.get("unit_def_id", 0),
                    "position": prior.get("position", (0.0, 0.0, 0.0)),
                }
        after = replace(after, units=units)
    record = evidence_record(
        scenario,
        result_status=int(result.status),
        before=before,
        after=after,
        evidence_source="state_stream",
        log_location=log_location,
    )
    if scenario.scenario_id in {"pause_match", "reject_lease_conflict"}:
        admin.execute_action(
            grpc_channel,
            token,
            pause_action(8100 + int(scenario.action.action_seq), False),
            timeout=timeout_seconds,
            admin_role="operator",
            client_id="admin-suite",
        )
    return record


def log_size(log_location: str) -> int:
    if not log_location:
        return 0
    try:
        return Path(log_location).stat().st_size
    except OSError:
        return 0


def wait_for_engine_speed(
    log_location: str,
    *,
    expected: float,
    start_offset: int,
    timeout: float,
) -> float:
    if not log_location:
        return 1.0
    deadline = time.monotonic() + timeout
    expected_text = f"Speed set to {expected:.1f}"
    while time.monotonic() < deadline:
        try:
            with Path(log_location).open("r", encoding="utf-8", errors="replace") as log:
                log.seek(start_offset)
                text = log.read()
        except OSError:
            text = ""
        if expected_text in text:
            return expected
        time.sleep(0.05)
    return 1.0


def missing_records_for_error(error: str, *, log_location: str = "") -> list[Any]:
    records = []
    for scenario in all_scenarios():
        record = missing_evidence_record(scenario, log_location=log_location)
        record.diagnostics.append(error)
        records.append(record)
    return records
