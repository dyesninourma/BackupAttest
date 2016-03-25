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
