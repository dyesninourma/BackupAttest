"""Assemble a recovery chain for a target time and find where none can be built.

A recovery chain for a target time T is the sequence of backups you would apply
to restore the system to its state at or before T:

  1. Start from the most recent full backup taken at or before T.
  2. Apply, in timestamp order, every incremental taken after that full and at or
     before T whose parent link resolves back to that full.

If there is no full backup at or before T, no chain can be assembled: that is a
gap. An incremental whose parent id does not exist, or whose parent is not the
full that governs its window, is orphaned and cannot contribute to a chain.

The hard case is a chain that looks complete because each job reported success,
yet an incremental in the middle points at a parent that was never taken. This
module resolves the parent link explicitly rather than assuming adjacency, so a
broken link surfaces as an orphan instead of a silently accepted chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .manifest import Entry


@dataclass(frozen=True)
class Chain:
    """A recovery chain assembled for a target time."""

    target: datetime
    base: Entry | None
    increments: tuple[Entry, ...]

    @property
    def assembled(self) -> bool:
        """True when a base full exists so a restore is possible."""
        return self.base is not None

    @property
    def recovery_point(self) -> datetime | None:
        """Timestamp of the newest backup in the chain, the state you recover to."""
        if self.base is None:
            return None
        if self.increments:
            return self.increments[-1].timestamp
        return self.base.timestamp

    @property
    def members(self) -> tuple[Entry, ...]:
        if self.base is None:
            return ()
        return (self.base, *self.increments)


@dataclass(frozen=True)
class Orphan:
    """An incremental that cannot attach to a governing full."""

    entry: Entry
    reason: str


def latest_full_before(entries: list[Entry], target: datetime) -> Entry | None:
    """Return the newest full backup taken at or before target, or None."""
    candidates = [e for e in entries if e.is_full and e.timestamp <= target]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e.timestamp)


def build_chain(entries: list[Entry], target: datetime) -> Chain:
    """Assemble the recovery chain for target.

    Increments are included only when their parent link resolves back to the
    governing full, directly or through a run of incrementals rooted at it.
    """
    base = latest_full_before(entries, target)
    if base is None:
        return Chain(target=target, base=None, increments=())

    by_id = {e.id: e for e in entries}
    rooted = {base.id}
    increments: list[Entry] = []
    # Walk incrementals in timestamp order; an incr joins the chain if its parent
    # is already rooted at this full and it falls within the window.
    for entry in sorted(entries, key=lambda e: (e.timestamp, e.id)):
        if not entry.is_incr:
            continue
        if entry.timestamp <= base.timestamp or entry.timestamp > target:
            continue
        parent = by_id.get(entry.parent)
        if parent is None:
            continue
        if entry.parent in rooted:
            rooted.add(entry.id)
            increments.append(entry)
    increments.sort(key=lambda e: (e.timestamp, e.id))
    return Chain(target=target, base=base, increments=tuple(increments))


def find_orphans(entries: list[Entry]) -> list[Orphan]:
    """Find incrementals that cannot attach to any full.

    An incremental is orphaned when its parent id does not exist, or when
    following parent links never reaches a full backup.
    """
    by_id = {e.id: e for e in entries}
    orphans: list[Orphan] = []
    for entry in entries:
        if not entry.is_incr:
            continue
        seen: set[str] = set()
        cursor: Entry | None = entry
        reason = ""
        while cursor is not None and cursor.is_incr:
            if cursor.parent not in by_id:
                reason = f"parent {cursor.parent!r} does not exist"
                cursor = None
                break
            if cursor.parent in seen:
                reason = f"parent chain loops at {cursor.parent!r}"
