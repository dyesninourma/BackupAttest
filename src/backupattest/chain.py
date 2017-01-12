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
