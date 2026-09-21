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


def achieved_rpo(
    entries: list[Entry],
    declared: timedelta,
    window_start: datetime,
    window_end: datetime,
) -> RpoResult:
    """Measure the widest gap between recoverable points inside the window.

    The window edges count: the span from window_start to the first point, and
    from the last point to window_end, are both real exposure. A missing backup
    shows up as the widest interior gap.
    """
    points = [p for p in _recoverable_points(entries) if window_start <= p <= window_end]
    edges = [window_start] + points + [window_end]
    worst = timedelta(0)
    worst_start: datetime | None = None
    worst_end: datetime | None = None
    for earlier, later in zip(edges, edges[1:]):
        span = later - earlier
        if span > worst:
            worst = span
            worst_start = earlier
            worst_end = later
    return RpoResult(
        declared=declared,
        achieved=worst,
        worst_start=worst_start,
        worst_end=worst_end,
    )


def format_duration(delta: timedelta) -> str:
    """Render a timedelta as a compact h/m string, deterministic and unit tagged."""
    total = int(delta.total_seconds())
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    if hours and minutes:
        return f"{hours}h{minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"
