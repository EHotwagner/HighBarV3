# SPDX-License-Identifier: GPL-2.0-only
"""Execution-layer capture helpers for live and synthetic Itertesting runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .bootstrap import BootstrapContext
from .itertesting_types import LiveExecutionCapture
from .metadata_records import (
    metadata_envelope,
    metadata_rows_for_envelopes,
    split_command_and_metadata_rows,
)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def metadata_envelopes_from_bootstrap_context(
    ctx: BootstrapContext | None,
) -> tuple:
    if ctx is None:
        return ()
    envelopes = []
    if ctx.bootstrap_readiness:
        envelopes.append(
            metadata_envelope(
                record_type="bootstrap_readiness",
                payload=ctx.bootstrap_readiness,
                sequence_index=len(envelopes),
            )
        )
    if ctx.runtime_capability_profile:
        envelopes.append(
            metadata_envelope(
                record_type="runtime_capability_profile",
                payload=ctx.runtime_capability_profile,
                sequence_index=len(envelopes),
            )
        )
    for item in ctx.callback_diagnostics:
        envelopes.append(
            metadata_envelope(
                record_type="callback_diagnostic",
                payload=item,
                sequence_index=len(envelopes),
            )
        )
    for item in ctx.prerequisite_resolution_records:
        envelopes.append(
            metadata_envelope(
                record_type="prerequisite_resolution",
                payload=item,
                sequence_index=len(envelopes),
            )
        )
    for item in ctx.map_source_decisions:
        envelopes.append(
            metadata_envelope(
                record_type="map_source_decision",
                payload=item,
                sequence_index=len(envelopes),
            )
        )
    return tuple(envelopes)


def metadata_rows_from_bootstrap_context(
    ctx: BootstrapContext | None,
) -> list[dict[str, Any]]:
    return metadata_rows_for_envelopes(metadata_envelopes_from_bootstrap_context(ctx))


def build_live_execution_capture(
    *,
    run_id: str,
    setup_mode: str,
    live_rows: list[dict[str, Any]] | None,
    collection_notes: tuple[str, ...] = (),
) -> LiveExecutionCapture:
    command_rows, metadata_records = split_command_and_metadata_rows(live_rows)
    return LiveExecutionCapture(
        run_id=run_id,
        setup_mode=setup_mode,  # type: ignore[arg-type]
        command_rows=command_rows,
        metadata_records=metadata_records,
        collection_notes=collection_notes,
        collected_at=utc_now_iso(),
    )
