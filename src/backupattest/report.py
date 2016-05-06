"""Render results as deterministic, line oriented text.

Every function returns a list of lines so callers join with a single newline and
results diff cleanly in git. No wall clock time enters the output except the
`now` the caller passes in explicitly.
"""

from __future__ import annotations

from datetime import datetime

from .chain import Chain
from .checks import Report
from .rpo import format_duration


def _ts(value: datetime) -> str:
    return f"{value:%Y-%m-%dT%H:%M:%SZ}"


def render_chain(chain: Chain) -> list[str]:
    """Render one assembled recovery chain for a target time."""
    lines = [f"target {_ts(chain.target)}"]
    if not chain.assembled:
        lines.append("  no chain: no full backup at or before the target")
