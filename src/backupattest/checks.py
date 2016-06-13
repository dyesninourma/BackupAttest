"""Aggregate the findings that decide whether you could actually restore.

Findings are the concrete answers to the blunt question. Each finding has a code
so results are stable and greppable:

- G001 gap:            a span of the window with no full to restore from
- O001 orphan:         an incremental whose parent chain never reaches a full
- R001 rpo:            achieved recovery point objective worse than declared
- V001 unverified:     a backup whose digest was never checked
- D001 stale drill:    the last successful drill is older than the declared interval
- D002 no drill:       no successful restore drill exists at all

A run is clean when there are no findings. Any finding drives the exit code to 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .chain import Gap, Orphan, find_gaps, find_orphans
from .drills import DrillLog
from .manifest import Entry
from .rpo import RpoResult, achieved_rpo, format_duration


@dataclass(frozen=True)
class Finding:
    """One thing that means you might not be able to restore."""

    code: str
    message: str

