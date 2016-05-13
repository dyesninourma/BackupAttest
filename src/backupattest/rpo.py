"""Compute achieved recovery point objective and compare against the declared one.

The recovery point objective (RPO) is the largest amount of data, measured in
time, that you accept losing. A declared RPO of 24 hours means: at any moment,
there should be a recoverable state no older than 24 hours behind now.

The achieved RPO is the real worst case: the widest gap between consecutive
recoverable points across the sample window. If backups land every 6 hours the
achieved RPO is about 6 hours. If one backup is missing, the gap on either side
of the hole widens and the achieved RPO gets worse.

This module measures the achieved RPO from the actual backup timestamps and
reports whether it meets the declared target.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .manifest import Entry


@dataclass(frozen=True)
class RpoResult:
    """Achieved recovery point objective against the declared target."""

    declared: timedelta
    achieved: timedelta
    worst_start: datetime | None
    worst_end: datetime | None

    @property
    def meets(self) -> bool:
        return self.achieved <= self.declared


def _recoverable_points(entries: list[Entry]) -> list[datetime]:
    """Timestamps at which a restore lands, sorted. Every backup is a point."""
    return sorted(e.timestamp for e in entries)

