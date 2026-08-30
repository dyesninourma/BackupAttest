"""Parse a backup manifest into typed entries.

The manifest is a line oriented text format so it diffs cleanly in git. Each
non blank, non comment line describes one backup:

    <kind> <id> <timestamp> <size> <digest> <verified> [parent]

Fields are separated by one or more spaces. Meaning:

- kind:       "full" or "incr"
- id:         a short identifier unique within the manifest
- timestamp:  ISO 8601 in UTC, seconds precision, e.g. 2026-08-01T00:00:00Z
- size:       bytes, a non negative integer
- digest:     the recorded content digest, e.g. sha256:abcd... (opaque here)
- verified:   "yes" or "no", whether the digest was ever checked against the bytes
- parent:     for incr only, the id of the backup it was taken against

Lines beginning with "#" are comments. Blank lines are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class ManifestError(ValueError):
    """Raised when a manifest line cannot be parsed."""


@dataclass(frozen=True)
class Entry:
    """One backup recorded in the manifest."""

    kind: str
    id: str
    timestamp: datetime
    size: int
    digest: str
    verified: bool
    parent: str | None

    @property
    def is_full(self) -> bool:
        return self.kind == "full"

    @property
    def is_incr(self) -> bool:
        return self.kind == "incr"


def parse_timestamp(text: str) -> datetime:
    """Parse a UTC ISO 8601 timestamp with a trailing Z."""
    if not _TS.match(text):
        raise ManifestError(f"bad timestamp: {text!r}")
    naive = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    return naive.replace(tzinfo=timezone.utc)


def parse_line(line: str, lineno: int) -> Entry:
    """Parse a single manifest data line into an Entry."""
    parts = line.split()
    if len(parts) < 6:
        raise ManifestError(f"line {lineno}: expected at least 6 fields, got {len(parts)}")
    kind, ident, ts, size, digest, verified = parts[:6]
    parent = parts[6] if len(parts) > 6 else None

    if kind not in ("full", "incr"):
        raise ManifestError(f"line {lineno}: kind must be full or incr, got {kind!r}")
    if verified not in ("yes", "no"):
        raise ManifestError(f"line {lineno}: verified must be yes or no, got {verified!r}")
    try:
        size_val = int(size)
    except ValueError:
        raise ManifestError(f"line {lineno}: size not an integer: {size!r}") from None
    if size_val < 0:
        raise ManifestError(f"line {lineno}: size is negative: {size_val}")

    if kind == "full" and parent is not None:
        raise ManifestError(f"line {lineno}: full backup {ident!r} must not name a parent")
    if kind == "incr" and parent is None:
        raise ManifestError(f"line {lineno}: incremental {ident!r} must name a parent")

    return Entry(
        kind=kind,
        id=ident,
        timestamp=parse_timestamp(ts),
        size=size_val,
        digest=digest,
        verified=verified == "yes",
        parent=parent,
    )


def parse_manifest(text: str) -> list[Entry]:
    """Parse the whole manifest, returning entries sorted by timestamp then id.

    Duplicate ids are rejected because the recovery chain relies on ids being
    unique keys.
    """
    entries: list[Entry] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entry = parse_line(stripped, lineno)
        if entry.id in seen:
            raise ManifestError(f"line {lineno}: duplicate id {entry.id!r}")
        seen.add(entry.id)
        entries.append(entry)
    entries.sort(key=lambda e: (e.timestamp, e.id))
    return entries


def load_manifest(path: str) -> list[Entry]:
    """Read and parse a manifest file from disk."""
    with open(path, "r", encoding="utf-8") as handle:
        return parse_manifest(handle.read())
