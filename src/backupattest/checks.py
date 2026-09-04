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


@dataclass
class Report:
    """The full set of findings plus the data needed to render them."""

    gaps: list[Gap] = field(default_factory=list)
    orphans: list[Orphan] = field(default_factory=list)
    rpo: RpoResult | None = None
    unverified: list[Entry] = field(default_factory=list)
    stale_drill: bool = False
    last_drill: datetime | None = None
    no_drill: bool = False

    def findings(self) -> list[Finding]:
        out: list[Finding] = []
        for gap in self.gaps:
            out.append(
                Finding(
                    "G001",
                    f"gap {gap.start:%Y-%m-%dT%H:%M:%SZ} to {gap.end:%Y-%m-%dT%H:%M:%SZ}: {gap.reason}",
                )
            )
        for orphan in self.orphans:
            out.append(
                Finding(
                    "O001",
                    f"orphan {orphan.entry.id} at {orphan.entry.timestamp:%Y-%m-%dT%H:%M:%SZ}: {orphan.reason}",
                )
            )
        if self.rpo is not None and not self.rpo.meets:
            out.append(
                Finding(
                    "R001",
                    f"achieved RPO {format_duration(self.rpo.achieved)} exceeds declared "
                    f"{format_duration(self.rpo.declared)}",
                )
            )
        for entry in self.unverified:
            out.append(
                Finding(
                    "V001",
                    f"unverified digest on {entry.id} ({entry.digest})",
                )
            )
        if self.no_drill:
            out.append(Finding("D002", "no successful restore drill on record"))
        elif self.stale_drill:
            last = self.last_drill
            out.append(
                Finding(
                    "D001",
                    f"last successful drill {last:%Y-%m-%dT%H:%M:%SZ} is outside the declared interval",
                )
            )
        return out

    @property
    def clean(self) -> bool:
        return not self.findings()


def unverified_backups(entries: list[Entry]) -> list[Entry]:
    """Backups whose digest was never checked, sorted for stable output."""
    out = [e for e in entries if not e.verified]
    out.sort(key=lambda e: (e.timestamp, e.id))
    return out


def drill_is_stale(log: DrillLog, now: datetime) -> tuple[bool, datetime | None, bool]:
    """Decide whether the last successful drill falls inside the declared interval.

    Returns (stale, last_ok_timestamp, no_drill). A drill is stale when the most
    recent ok drill is older than interval_days before now. no_drill is True when
    no ok drill exists at all.
    """
    last = log.last_ok
    if last is None:
        return False, None, True
    deadline = now - timedelta(days=log.interval_days)
    return last.timestamp < deadline, last.timestamp, False


def build_report(
    entries: list[Entry],
    log: DrillLog,
    declared_rpo: timedelta,
    window_start: datetime,
    window_end: datetime,
    now: datetime,
) -> Report:
    """Run every check and collect the findings into one report."""
    stale, last, none = drill_is_stale(log, now)
    return Report(
        gaps=find_gaps(entries, window_start, window_end),
        orphans=find_orphans(entries),
        rpo=achieved_rpo(entries, declared_rpo, window_start, window_end),
        unverified=unverified_backups(entries),
        stale_drill=stale,
        last_drill=last,
        no_drill=none,
    )
