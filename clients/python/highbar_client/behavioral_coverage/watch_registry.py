# SPDX-License-Identifier: GPL-2.0-only
"""Filesystem-backed active watch index for attach-later selection."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .itertesting_types import ActiveWatchIndex, ActiveWatchIndexEntry, WatchedRunSession


ACTIVE_WATCH_INDEX_NAME = "active-watch-sessions.json"


@dataclass(frozen=True)
class WatchSelectionResult:
    run_id: str | None
    selection_mode: str
    reason: str
    entry: ActiveWatchIndexEntry | None
    compatible_entries: tuple[ActiveWatchIndexEntry, ...] = ()


def active_watch_index_path(reports_dir: Path) -> Path:
    return reports_dir / ACTIVE_WATCH_INDEX_NAME


def _empty_index(reports_dir: Path, *, generated_at: str = "") -> ActiveWatchIndex:
    return ActiveWatchIndex(
        generated_at=generated_at,
        entries=(),
        source_reports_dir=str(reports_dir),
    )


def _index_entry_from_dict(payload: dict[str, object]) -> ActiveWatchIndexEntry:
    return ActiveWatchIndexEntry(
        run_id=str(payload["run_id"]),
        campaign_id=payload.get("campaign_id"),  # type: ignore[arg-type]
        watch_state=str(payload.get("watch_state", "unavailable")),  # type: ignore[arg-type]
        compatible_for_attach=bool(payload.get("compatible_for_attach", False)),
        selection_summary=str(payload.get("selection_summary", "")),
        updated_at=str(payload.get("updated_at", "")),
        report_path=str(payload.get("report_path", "")),
        manifest_path=str(payload.get("manifest_path", "")),
    )


def load_active_watch_index(reports_dir: Path) -> ActiveWatchIndex:
    path = active_watch_index_path(reports_dir)
    if not path.exists():
        return _empty_index(reports_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ActiveWatchIndex(
        generated_at=payload.get("generated_at", ""),
        entries=tuple(
            _index_entry_from_dict(item) for item in payload.get("entries", ())
        ),
        source_reports_dir=payload.get("source_reports_dir", str(reports_dir)),
    )


def write_active_watch_index(
    reports_dir: Path,
    index: ActiveWatchIndex,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = active_watch_index_path(reports_dir)
    path.write_text(
        json.dumps(asdict(index), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def session_to_index_entry(
    session: WatchedRunSession,
    *,
    updated_at: str,
    manifest_path: str = "",
) -> ActiveWatchIndexEntry:
    viewer = session.viewer_access
    if session.run_lifecycle_state == "completed":
        watch_state = "completed"
        compatible = False
    elif session.run_lifecycle_state == "expired" or (
        viewer is not None and viewer.availability_state == "expired"
    ):
        watch_state = "expired"
        compatible = False
    elif viewer is not None and viewer.availability_state in {"available", "attached"}:
        watch_state = "active"
        compatible = True
    else:
        watch_state = "unavailable"
        compatible = False
    reason = viewer.reason if viewer is not None else (
        session.preflight_result.reason if session.preflight_result is not None else "watch state unavailable"
    )
    summary = (
        f"run={session.run_id} campaign={session.campaign_id or 'none'} "
        f"state={watch_state} reason={reason}"
    )
    return ActiveWatchIndexEntry(
        run_id=session.run_id,
        campaign_id=session.campaign_id,
        watch_state=watch_state,
        compatible_for_attach=compatible,
        selection_summary=summary,
        updated_at=updated_at,
        report_path=session.report_path,
        manifest_path=manifest_path,
    )


def upsert_watch_session(
    reports_dir: Path,
    session: WatchedRunSession,
    *,
    updated_at: str,
    manifest_path: str = "",
) -> ActiveWatchIndex:
    current = load_active_watch_index(reports_dir)
    entry = session_to_index_entry(
        session,
        updated_at=updated_at,
        manifest_path=manifest_path,
    )
    retained = [item for item in current.entries if item.run_id != session.run_id]
    retained.append(entry)
    retained.sort(key=lambda item: item.run_id)
    updated = ActiveWatchIndex(
        generated_at=updated_at,
        entries=tuple(retained),
        source_reports_dir=current.source_reports_dir or str(reports_dir),
    )
    write_active_watch_index(reports_dir, updated)
    return updated


def resolve_attach_later_target(
    reports_dir: Path,
    *,
    run_id: str | None,
) -> WatchSelectionResult:
    index = load_active_watch_index(reports_dir)
    compatible = tuple(
        item for item in index.entries if item.compatible_for_attach
    )
    if run_id:
        for entry in index.entries:
            if entry.run_id != run_id:
                continue
            if entry.compatible_for_attach:
                return WatchSelectionResult(
                    run_id=entry.run_id,
                    selection_mode="explicit",
                    reason=f"resolved explicit watch run '{entry.run_id}'",
                    entry=entry,
                    compatible_entries=compatible,
                )
            return WatchSelectionResult(
                run_id=None,
                selection_mode="explicit",
                reason=f"run '{run_id}' is not attachable: {entry.selection_summary}",
                entry=entry,
                compatible_entries=compatible,
            )
        return WatchSelectionResult(
            run_id=None,
            selection_mode="explicit",
            reason=f"run '{run_id}' is not present in {ACTIVE_WATCH_INDEX_NAME}",
            entry=None,
            compatible_entries=compatible,
        )
    if len(compatible) == 1:
        return WatchSelectionResult(
            run_id=compatible[0].run_id,
            selection_mode="single-active-auto",
            reason=f"auto-selected the only compatible active run '{compatible[0].run_id}'",
            entry=compatible[0],
            compatible_entries=compatible,
        )
    if len(compatible) > 1:
        candidates = ", ".join(item.run_id for item in compatible)
        return WatchSelectionResult(
            run_id=None,
            selection_mode="ambiguous",
            reason=(
                "attach-later is ambiguous; specify --watch-run <run-id>. "
                f"Compatible runs: {candidates}"
            ),
            entry=None,
            compatible_entries=compatible,
        )
    return WatchSelectionResult(
        run_id=None,
        selection_mode="single-active-auto",
        reason="no compatible active watched runs found",
        entry=None,
        compatible_entries=compatible,
    )
