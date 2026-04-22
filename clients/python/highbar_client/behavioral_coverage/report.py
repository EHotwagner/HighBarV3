# SPDX-License-Identifier: GPL-2.0-only
"""Canonical CSV + digest emitter for the behavioral-coverage report.

Contract: contracts/behavioral-coverage-csv.md.

Digest: SHA-256 over the 4 reproducibility-critical columns with ASCII
unit-separator (0x1F) as field delimiter and LF as row terminator.
Artifact CSV: RFC 4180 quoting; 66 data rows in ascending arm_name
byte order.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import sys
from pathlib import Path
from typing import Iterable, Sequence

from .types import CoverageReportError, VerificationOutcome

# Column schema — kept in sync with contracts/behavioral-coverage-csv.md §1.
CSV_HEADER = ("arm_name", "category", "dispatched", "verified",
              "evidence", "error")


# Consistency rules (§1 Consistency rules) — enforced at write time.
_VALID_VERIFIED = {"true", "false", "na"}
_ERRORS_FOR_FALSE = {"effect_not_observed", "target_unit_destroyed",
                       "timeout", "internal_error"}
_ERRORS_FOR_NA = {"dispatcher_rejected", "cheats_required",
                    "precondition_unmet", "bootstrap_reset_failed",
                    "not_wire_observable"}


def _validate_row(row: dict) -> None:
    v = row["verified"]
    if v not in _VALID_VERIFIED:
        raise CoverageReportError(
            f"{row['arm_name']}: verified={v!r} not in {_VALID_VERIFIED}"
        )
    d = row["dispatched"]
    if d not in ("true", "false"):
        raise CoverageReportError(
            f"{row['arm_name']}: dispatched={d!r} not in {{'true','false'}}"
        )
    e = row["error"]
    if d == "false" and v != "na":
        raise CoverageReportError(
            f"{row['arm_name']}: dispatched=false requires verified=na "
            f"(got verified={v})"
        )
    if v == "true" and e != "":
        raise CoverageReportError(
            f"{row['arm_name']}: verified=true requires error='' (got {e!r})"
        )
    if v == "false":
        if e not in _ERRORS_FOR_FALSE:
            raise CoverageReportError(
                f"{row['arm_name']}: verified=false requires error in "
                f"{_ERRORS_FOR_FALSE} (got {e!r})"
            )
    elif v == "na":
        if e not in _ERRORS_FOR_NA:
            raise CoverageReportError(
                f"{row['arm_name']}: verified=na requires error in "
                f"{_ERRORS_FOR_NA} (got {e!r})"
            )


# ---- canonical digest ---------------------------------------------------


def canonical_digest(rows: Iterable[tuple[str, str, str, str]]) -> str:
    """Reference implementation from contracts/behavioral-coverage-csv.md §3.

    rows: iterable of (arm_name, dispatched, verified, error) tuples.
    Returns: 64-char lowercase hex SHA-256.
    """
    sorted_rows = sorted(rows, key=lambda r: r[0].encode("utf-8"))
    buf = bytearray()
    for arm_name, dispatched, verified, error in sorted_rows:
        if dispatched not in ("true", "false"):
            raise CoverageReportError(
                f"digest: {arm_name!r} dispatched={dispatched!r}"
            )
        if verified not in ("true", "false", "na"):
            raise CoverageReportError(
                f"digest: {arm_name!r} verified={verified!r}"
            )
        buf += arm_name.encode("utf-8")
        buf += b"\x1f"
        buf += dispatched.encode("ascii")
        buf += b"\x1f"
        buf += verified.encode("ascii")
        buf += b"\x1f"
        buf += error.encode("utf-8")
        buf += b"\n"
    return hashlib.sha256(bytes(buf)).hexdigest()


# ---- CSV writer ---------------------------------------------------------


def _sort_rows(rows: Sequence[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: r["arm_name"].encode("utf-8"))


def write_csv(path: Path | str, rows: Sequence[dict]) -> None:
    """Emit the CSV artifact per contracts/behavioral-coverage-csv.md §1.

    - UTF-8, no BOM.
    - LF line terminator (no CRLF).
    - Terminating LF after the final row.
    - RFC 4180 quoting for cells with commas/quotes/newlines.
    - Sorted by arm_name ascending.

    Validates each row's consistency rules before writing; raises
    CoverageReportError on violation (driver returns exit 2).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = _sort_rows(rows)
    for r in sorted_rows:
        _validate_row(r)
    # Build the CSV in-memory then write atomically so a crashed
    # emitter never leaves a half-written file.
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=CSV_HEADER,
                             lineterminator="\n",
                             quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for r in sorted_rows:
        writer.writerow({k: r.get(k, "") for k in CSV_HEADER})
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(buf.getvalue(), encoding="utf-8")
    os.replace(tmp, p)


def write_digest(path: Path | str, hex_digest: str) -> None:
    """Write exactly 64 hex chars + LF. See contract §2."""
    if len(hex_digest) != 64 or not all(
            c in "0123456789abcdef" for c in hex_digest):
        raise CoverageReportError(
            f"digest must be 64 lowercase hex chars, got len={len(hex_digest)}"
        )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(hex_digest + "\n", encoding="ascii")


def digest_from_csv(csv_path: Path | str) -> str:
    """Read a CSV artifact and recompute the canonical digest from its
    4 critical columns. Used by --verify / --diff.
    """
    p = Path(csv_path)
    rows: list[tuple[str, str, str, str]] = []
    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((r["arm_name"], r["dispatched"],
                         r["verified"], r["error"]))
    return canonical_digest(rows)


# ---- summary ------------------------------------------------------------


def summarize(rows: Sequence[dict], threshold: float) -> tuple[bool, str]:
    """Return (pass, summary_line).

    pass = rate >= threshold. Rate denominator is wire_observable =
    rows where verified in {'true','false'} (na rows excluded per
    FR-005 / FR-007).
    """
    verified = sum(1 for r in rows if r["verified"] == "true")
    wire_observable = sum(1 for r in rows if r["verified"] in ("true", "false"))
    rate = (verified / wire_observable) if wire_observable > 0 else 0.0
    ok = rate >= threshold
    pct = rate * 100.0
    tpct = threshold * 100.0
    status = "PASS" if ok else f"below threshold {tpct:.1f}% — FAIL"
    line = (f"behavioral-coverage: verified={verified}/{wire_observable} "
            f"({pct:.1f}%) threshold={tpct:.1f}% — {status}")
    return ok, line


# ---- CLI subcommands (FR-010 tooling) -----------------------------------


def _cmd_verify(args: argparse.Namespace) -> int:
    csv_p = Path(args.csv)
    digest_p = Path(args.digest) if args.digest else csv_p.with_suffix(".digest")
    if not csv_p.exists() or not digest_p.exists():
        print(f"missing {csv_p} or {digest_p}", file=sys.stderr)
        return 2
    expected = digest_p.read_text(encoding="ascii").strip()
    actual = digest_from_csv(csv_p)
    if expected != actual:
        print(f"digest mismatch: csv={actual} sidecar={expected}",
              file=sys.stderr)
        return 1
    print(f"digest OK: {actual}")
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    a = Path(args.a)
    b = Path(args.b)
    with a.open("r", encoding="utf-8", newline="") as fa, \
         b.open("r", encoding="utf-8", newline="") as fb:
        ra = {r["arm_name"]: r for r in csv.DictReader(fa)}
        rb = {r["arm_name"]: r for r in csv.DictReader(fb)}
    names = sorted(set(ra) | set(rb))
    any_diff = False
    for n in names:
        ar = ra.get(n, {})
        br = rb.get(n, {})
        for col in ("dispatched", "verified", "error"):
            if ar.get(col) != br.get(col):
                any_diff = True
                print(f"{n} {col}: {ar.get(col)} != {br.get(col)}")
    return 0 if not any_diff else 1


def _cmd_summary(args: argparse.Namespace) -> int:
    p = Path(args.csv)
    with p.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    ok, line = summarize(rows, args.threshold)
    print(line)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="highbar_client.behavioral_coverage.report")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="recompute digest from CSV + compare")
    v.add_argument("csv")
    v.add_argument("--digest", help="override digest sidecar path")
    v.set_defaults(func=_cmd_verify)

    d = sub.add_parser("diff", help="pretty-print diff of two CSVs")
    d.add_argument("a")
    d.add_argument("b")
    d.set_defaults(func=_cmd_diff)

    s = sub.add_parser("summary", help="print summary line from CSV")
    s.add_argument("csv")
    s.add_argument("--threshold", type=float, default=0.50)
    s.set_defaults(func=_cmd_summary)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "CSV_HEADER",
    "canonical_digest",
    "write_csv",
    "write_digest",
    "digest_from_csv",
    "summarize",
    "main",
]
