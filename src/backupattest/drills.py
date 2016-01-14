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
