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
        return lines
    assert chain.base is not None
    lines.append(f"  base   {chain.base.id} full {_ts(chain.base.timestamp)}")
    for inc in chain.increments:
        lines.append(f"  apply  {inc.id} incr {_ts(inc.timestamp)} parent {inc.parent}")
    point = chain.recovery_point
    lines.append(f"  recovers to {_ts(point)}" if point else "  recovers to (none)")
    lines.append(f"  steps {len(chain.members)}")
    return lines


def render_report(report: Report) -> list[str]:
    """Render the coverage report: findings first, then a summary line."""
    lines: list[str] = []
    findings = report.findings()
    if report.rpo is not None:
        lines.append(
            f"rpo declared {format_duration(report.rpo.declared)} "
            f"achieved {format_duration(report.rpo.achieved)} "
            f"{'ok' if report.rpo.meets else 'MISS'}"
        )
    lines.append(f"unverified backups {len(report.unverified)}")
    if report.no_drill:
        lines.append("last drill none")
    elif report.last_drill is not None:
        state = "stale" if report.stale_drill else "current"
        lines.append(f"last drill {_ts(report.last_drill)} {state}")
    lines.append("")
    if findings:
        lines.append(f"findings {len(findings)}")
        for finding in findings:
            lines.append(f"  {finding.code} {finding.message}")
    else:
        lines.append("findings 0 (clean)")
    return lines


def render_drills(report: Report) -> list[str]:
    """Render only the drill portion of a report."""
    lines: list[str] = []
    if report.no_drill:
        lines.append("last drill none")
        lines.append("  D002 no successful restore drill on record")
        return lines
    assert report.last_drill is not None
    state = "stale" if report.stale_drill else "current"
    lines.append(f"last drill {_ts(report.last_drill)} {state}")
    if report.stale_drill:
        lines.append(
            f"  D001 last successful drill {_ts(report.last_drill)} is outside the declared interval"
        )
    return lines
