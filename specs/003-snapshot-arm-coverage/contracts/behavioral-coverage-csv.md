# Contract: Behavioral-coverage CSV + digest

**Feature**: 003-snapshot-arm-coverage
**Consumes**: FR-004, FR-004a, FR-007, FR-008, FR-010, FR-012;
               data-model §5–§6; research.md §R5, §R7

This is the authoritative format for both artifacts the macro
driver emits. CI consumes both; the reproducibility gate (FR-008)
operates exclusively on the digest.

---

## 1. CSV artifact

### Location

```
build/reports/aicommand-behavioral-coverage.csv
```

For reproducibility runs, per-run subdirectories:

```
build/reports/run-1/aicommand-behavioral-coverage.csv
build/reports/run-2/aicommand-behavioral-coverage.csv
…
build/reports/run-5/aicommand-behavioral-coverage.csv
```

### Encoding

- UTF-8, no BOM.
- Line separator: LF (`\n`) only; no CRLF.
- RFC 4180 quoting: cells containing commas, double-quotes, or
  newlines are wrapped in `"…"`; embedded double-quotes are
  doubled (`""`).
- Terminating LF after the final row.

### Schema

Header (fixed, emitted verbatim):

```
arm_name,category,dispatched,verified,evidence,error
```

**Exactly 66 data rows** (FR-004), in ascending `arm_name` byte
order (UTF-8, case-sensitive).

Per-column rules:

| Column | Type | Allowed values / format |
|---|---|---|
| `arm_name` | string | exact oneof arm name from `AICommand` in `commands.proto` (e.g., `move_unit`) |
| `category` | string | `channel_a_command`, `channel_b_query`, `channel_c_lua` |
| `dispatched` | string | `true` or `false` (lowercase) |
| `verified` | string | `true`, `false`, or `na` (lowercase) |
| `evidence` | string | free-form; `.3f` formatting for floats; empty for rows where the predicate did not run (e.g., skipped) |
| `error` | string | empty, or one of: `dispatcher_rejected`, `effect_not_observed`, `target_unit_destroyed`, `cheats_required`, `precondition_unmet`, `bootstrap_reset_failed`, `not_wire_observable`, `timeout`, `internal_error` |

### Consistency rules enforced at emit time

- `dispatched=false` ⇒ `verified=na`.
- `verified=true` ⇒ `error=""` and `dispatched=true`.
- `verified=false` ⇒ `error` ∈ `{effect_not_observed,
  target_unit_destroyed, timeout, internal_error}` and
  `dispatched=true`.
- `verified=na` ⇒ `error` ∈ `{dispatcher_rejected,
  cheats_required, precondition_unmet, bootstrap_reset_failed,
  not_wire_observable}`.

The emitter asserts these at write time; any violation raises
`CoverageReportError` and aborts the run (exit code 2, distinct
from threshold failure's exit 1). This prevents a bug in the
driver from producing a silently-wrong CSV.

### Example (abbreviated, 3 of 66 rows shown)

```csv
arm_name,category,dispatched,verified,evidence,error
attack_unit,channel_a_command,true,true,"enemy_health before=4500.000 after=4480.500 delta=-19.500",
build_unit,channel_a_command,true,true,"unit_count_delta=+1 new_def=armmex under_construction=true build_progress=0.123",
move_unit,channel_a_command,true,true,"position dx=503.240 dz=0.000 (threshold 100)",
```

---

## 2. Digest sidecar

### Location

```
build/reports/aicommand-behavioral-coverage.digest
```

Per-run:

```
build/reports/run-1/aicommand-behavioral-coverage.digest
…
build/reports/run-5/aicommand-behavioral-coverage.digest
```

### Format

A single SHA-256 hex string, lowercase, followed by exactly one LF
terminator. Total file size: **65 bytes** (64 hex + 1 LF). No
leading whitespace, no trailing anything, no metadata.

Example file contents:

```
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

### Compatibility with `sha256sum`

The file is NOT in `sha256sum` output format (which would include
` filename` after the hash). This is intentional — the digest is
meant to be fed directly into `diff` or `cmp` across runs, not
into `sha256sum -c`. If a human needs to verify the digest against
the CSV, they run the driver's `report.py --verify` subcommand.

---

## 3. Canonical digest serialization

The digest is computed over the **canonical serialization** of the
reproducibility-critical columns. This is a different byte stream
from the CSV artifact — the CSV is optimised for humans and tools
(RFC 4180, readable), the canonical serialization is optimised for
bit-exact reproducibility.

### Algorithm

```
Input:  list of 66 rows, each a (arm_name, dispatched, verified, error) tuple
Output: 64-char lowercase hex SHA-256

1. Sort rows by ascending arm_name (UTF-8 byte order, case-sensitive).
2. For each row, concatenate the four columns with \x1f (ASCII unit
   separator, 0x1F) as the field delimiter. Append \n (0x0A) as row
   terminator.
   Per-column serialization:
     arm_name:   UTF-8 bytes of the string, no escaping (arm names
                 are guaranteed ASCII snake_case by proto conventions).
     dispatched: "true" or "false" (ASCII, lowercase, no quotes).
     verified:   "true", "false", or "na" (ASCII, lowercase, no quotes).
     error:      empty string OR one of the fixed lowercase
                 snake_case tokens; UTF-8 bytes, no escaping.
3. Concatenate all row byte strings in sort order into a single byte
   buffer.
4. SHA-256 hash the buffer; encode as 64 lowercase hex chars.
```

### Reference Python implementation

```python
import hashlib
from typing import Iterable

def canonical_digest(rows: Iterable[tuple[str, str, str, str]]) -> str:
    """Compute the reproducibility digest per contract.

    rows: iterable of (arm_name, dispatched, verified, error) tuples.
    Returns: 64-char lowercase hex.
    """
    sorted_rows = sorted(rows, key=lambda r: r[0].encode("utf-8"))
    buf = bytearray()
    for arm_name, dispatched, verified, error in sorted_rows:
        assert dispatched in ("true", "false")
        assert verified in ("true", "false", "na")
        buf += arm_name.encode("utf-8")
        buf += b"\x1f"
        buf += dispatched.encode("ascii")
        buf += b"\x1f"
        buf += verified.encode("ascii")
        buf += b"\x1f"
        buf += error.encode("utf-8")
        buf += b"\n"
    return hashlib.sha256(bytes(buf)).hexdigest()
```

### Why 0x1F (unit separator)?

- Guaranteed not to appear in any of the four column values
  (arm names are snake_case; the boolean/error vocabularies are
  fixed), so no escaping logic is needed.
- Cross-platform stable: always one byte, not affected by locale
  or Python CSV dialect settings.
- The digest is stable across any refactor of the CSV emitter's
  quoting or line-ending logic — the canonical bytes never touch
  the CSV code path.

### Explicitly excluded from the digest

- `category` column (derived constant, adds no information).
- `evidence` column (floating-point jitter is a test-implementation
  detail, not a correctness signal — spec clarification Q3).
- Run metadata: timestamp, hostname, commit SHA (these vary by
  design and are irrelevant to arm-coverage reproducibility).

---

## 4. Reproducibility gate (FR-008, US6)

The script `tests/headless/behavioral-reproducibility.sh`:

1. Invokes `aicommand-behavioral-coverage.sh` 5×, once per
   run-index N ∈ [1..5], all with `--gameseed 0x42424242` and
   separate `--output-dir build/reports/run-<N>`.
2. Reads the 5 digest files into memory.
3. Asserts all 5 are byte-identical. If not, prints a per-row diff
   of the 4 critical columns between run-1 (canonical) and the
   first differing run.
4. Exits 0 iff all 5 digests match AND the p50 framerate spread
   across runs is ≤ 5% (FR-009).

On digest mismatch, the per-row diff is produced by re-reading the
CSV artifacts (which carry the same 4 columns) rather than
re-computing the canonical serialization. This gives a
human-readable localization of the flaky arm(s).

---

## 5. Threshold evaluation (FR-007, US4)

`aicommand-behavioral-coverage.sh` evaluates the threshold from
the CSV, not from the digest:

```
verified_count     = |{row : row.verified == "true"}|
wire_observable    = |{row : row.verified in ("true", "false")}|
                     # "na" rows are excluded — not-wire-observable,
                     # precondition_unmet, etc.
rate               = verified_count / wire_observable_count
threshold          = HIGHBAR_BEHAVIORAL_THRESHOLD (default 0.50)
exit_code          = 0 if rate >= threshold else 1
```

Summary line printed to stdout on exit:

```
behavioral-coverage: verified=<N>/<W> (<P>%) threshold=<T>% — PASS
```

or

```
behavioral-coverage: verified=<N>/<W> (<P>%) below threshold <T>% — FAIL
```

CI then uploads both artifacts (CSV + digest) per FR-010.

---

## 6. Tooling notes

- `report.py --verify`: recompute the digest from the CSV and
  compare to the digest sidecar. Exit 0 on match. Used in the
  reproducibility script and by humans debugging a failing run.
- `report.py --diff a.csv b.csv`: pretty-print the row-by-row
  diff on the 4 critical columns, highlighting which arm(s)
  differ. Used by the reproducibility script on mismatch.
- `report.py --summary a.csv`: print the summary line without
  re-running the match. Used by CI's threshold-ratchet comment
  job.
