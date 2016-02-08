"""Parse a restore drill log.

A drill is a rehearsal in which someone actually restored from a backup and
confirmed the result, rather than trusting that the backup job reported success.
The log is line oriented:

    <timestamp> <backup_id> <outcome> [note...]

Meaning:

- timestamp:  ISO 8601 UTC with trailing Z, when the drill ran
- backup_id:  the id of the backup that was restored (should exist in the manifest)
- outcome:    "ok" if the restore verified, "fail" if it did not
- note:       optional free text, kept verbatim for the report

Lines beginning with "#" are comments. Blank lines are ignored.

The log also carries one directive line declaring the drill interval:

    interval <days>

That directive says how often a restore drill is supposed to happen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .manifest import ManifestError, parse_timestamp


class DrillError(ValueError):
    """Raised when a drill log line cannot be parsed."""


@dataclass(frozen=True)
class Drill:
    """One restore drill recorded in the log."""

    timestamp: datetime
    backup_id: str
    outcome: str
    note: str

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"


@dataclass(frozen=True)
class DrillLog:
    """A parsed drill log: the declared interval and the drills themselves."""

    interval_days: int
    drills: list[Drill]

    @property
    def last_ok(self) -> Drill | None:
        """The most recent drill with an ok outcome, or None."""
        oks = [d for d in self.drills if d.ok]
        return max(oks, key=lambda d: d.timestamp) if oks else None


def parse_drills(text: str) -> DrillLog:
    """Parse the whole drill log."""
    interval: int | None = None
    drills: list[Drill] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if parts[0] == "interval":
            if len(parts) != 2:
                raise DrillError(f"line {lineno}: interval takes one integer")
            try:
                interval = int(parts[1])
