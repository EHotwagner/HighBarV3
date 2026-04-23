# Phase 1 Data Model — BAR Live Run Viewer

**Branch**: `018-live-run-viewer` | **Date**: 2026-04-23  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

018 does not add a database or a new transport schema. It extends the existing filesystem-backed Itertesting bundle with explicit BNV watch configuration, preflight, active-session indexing, and viewer lifecycle records so maintainers can launch or reattach deterministically without relying on hidden process state.

---

## Entity: `WatchProfile`

The structured BNV launch configuration referenced by a watched run request.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `profile_id` | string | yes | Stable profile name such as `default` or `wide-monitor`. |
| `bnv_binary` | string | yes | Resolved path to the BAR Native Game Viewer executable, optionally inherited from `HIGHBAR_BNV_BINARY`. |
| `window_mode` | enum | yes | `windowed`, `borderless`, or `fullscreen`; default is `windowed`. |
| `window_width` | integer | yes | Default `1920`. |
| `window_height` | integer | yes | Default `1080`. |
| `mouse_capture` | boolean | yes | Default `false`. |
| `extra_launch_args` | array of string | no | Additional viewer arguments allowed by the profile. |
| `spectator_only` | boolean | yes | Must remain `true` for this feature. |

**Validation**:

- Default profile values must match the clarified spec.
- The profile may not enable controlling or gameplay-altering viewer behavior.

---

## Entity: `WatchRequest`

The maintainer’s request to watch either a newly launched live run or an already active run.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `request_id` | string | yes | Stable request identifier for logs and bundle traceability. |
| `request_mode` | enum | yes | `launch-time` or `attach-later`. |
| `requested_at` | timestamp | yes | When the request was made. |
| `target_run_id` | string \| null | no | Explicit run reference when provided. |
| `selection_mode` | enum | yes | `explicit`, `single-active-auto`, or `ambiguous`. |
| `profile_ref` | string | yes | Selected watch profile name or inline profile reference. |
| `watch_required` | boolean | yes | True when failure to launch BNV must fail or abort the run request. |

**Validation**:

- `selection_mode` must be `explicit` whenever more than one compatible active run exists.
- Launch-time requests may omit `target_run_id`; attach-later requests may auto-select only when one compatible run is active.

---

## Entity: `WatchPreflightResult`

The explicit readiness result evaluated before BNV launch begins.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `status` | enum | yes | `ready`, `profile_invalid`, `bnv_missing`, `environment_unready`, `run_incompatible`, or `selection_failed`. |
| `reason` | string | yes | User-readable explanation of the result. |
| `checked_at` | timestamp | yes | When readiness was evaluated. |
| `resolved_profile` | `WatchProfile` \| null | no | Present when profile parsing succeeded. |
| `resolved_run_id` | string \| null | no | Present when run selection succeeded. |
| `blocking` | boolean | yes | True for any status other than `ready`. |

**Validation**:

- Requested watch mode must not start live execution unless `status == ready`.
- Preflight reasons must be stable enough to render in stdout, manifest, and report surfaces.

---

## Entity: `ViewerAccessRecord`

The maintainer-visible lifecycle of one BNV access attempt for a run.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `availability_state` | enum | yes | `pending`, `available`, `attached`, `unavailable`, `expired`, or `disconnected`. |
| `reason` | string | yes | Human-readable explanation for the current state. |
| `launch_command` | array of string | no | Normalized command used to launch BNV when available. |
| `launched_at` | timestamp \| null | no | When BNV was launched. |
| `viewer_pid` | integer \| null | no | Local viewer PID when known. |
| `expires_at` | timestamp \| null | no | When access should be treated as no longer attachable. |
| `last_transition_at` | timestamp | yes | Timestamp of the latest state change. |

**Validation**:

- `availability_state` must never imply gameplay control.
- `unavailable` and `expired` states must carry a non-empty `reason`.

---

## Entity: `WatchedRunSession`

The run-bound summary that ties watch request, lifecycle, and run identity together.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Existing Itertesting run identifier. |
| `campaign_id` | string \| null | no | Existing campaign identifier when present. |
| `run_lifecycle_state` | enum | yes | `preflight`, `launching`, `active`, `completed`, `failed`, or `expired`. |
| `watch_requested` | boolean | yes | Whether watch mode was requested at all. |
| `watch_request` | `WatchRequest` \| null | no | Present when watch mode was requested. |
| `preflight_result` | `WatchPreflightResult` \| null | no | Present for watched runs. |
| `viewer_access` | `ViewerAccessRecord` \| null | no | Present once watch state becomes visible. |
| `report_path` | string | yes | Existing `run-report.md` location for diagnosis. |

**Validation**:

- Watched sessions must preserve the exact existing `run_id` and `campaign_id`.
- A requested watch session that never passes preflight must still produce a diagnosable record.

---

## Entity: `ActiveWatchIndexEntry`

The attach-later discovery record for one active or recently active watchable run.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Key for attach-later selection. |
| `campaign_id` | string \| null | no | Optional campaign grouping. |
| `watch_state` | enum | yes | `active`, `available`, `unavailable`, `expired`, or `completed`. |
| `compatible_for_attach` | boolean | yes | Whether attach-later may still launch BNV. |
| `selection_summary` | string | yes | Short maintainer-facing disambiguation text. |
| `updated_at` | timestamp | yes | Last refresh time for the entry. |

**Validation**:

- Only entries with `compatible_for_attach == true` may participate in single-run auto-selection.
- Completed or expired sessions must not remain attachable in the active index.

---

## Entity: `ActiveWatchIndex`

The filesystem-backed index used to resolve attach-later requests across current runs.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `generated_at` | timestamp | yes | When the index snapshot was written. |
| `entries` | array of `ActiveWatchIndexEntry` | yes | All known active or recently active watchable runs. |
| `source_reports_dir` | string | yes | Root reports directory that owns the index. |

**Validation**:

- The index must be writable from separate command invocations.
- The index must not become the only durable record; per-run bundle data remains authoritative after completion.

---

## Relationships

```text
WatchRequest
└── WatchProfile

WatchPreflightResult
├── WatchProfile
└── resolved_run_id

WatchedRunSession
├── WatchRequest
├── WatchPreflightResult
└── ViewerAccessRecord

ActiveWatchIndex
└── ActiveWatchIndexEntry[]
     └── WatchedRunSession.run_id
```

018 keeps the existing Itertesting bundle as the maintainer-facing truth, while adding explicit watch configuration, preflight, and active-session indexing so BNV launch and attach-later selection remain deterministic and diagnosable.
