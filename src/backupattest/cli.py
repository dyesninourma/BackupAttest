"""Command line interface for backupattest.

Subcommands:

- chain     assemble the recovery chain for a target time and print it
- coverage  run every check and print the full findings report
- drills    check only the restore drill freshness
- version   print the version

Exit codes: 0 clean, 1 findings present, 2 usage error.

Time inputs are explicit so output is deterministic. `--now` fixes the moment the
drill freshness is measured against; it defaults to the newest backup timestamp.
The sample window defaults to the first and last backup timestamps and can be
overridden with --window-start and --window-end.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta

from . import __version__
from .chain import build_chain
from .checks import build_report
from .drills import DrillError, load_drills
from .manifest import ManifestError, load_manifest, parse_timestamp
from .report import render_chain, render_drills, render_report


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{raw!r} is not an integer")
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive number of hours")
    return value


def _window(entries, args):
    """Resolve the sample window from flags or the manifest span."""
    start = parse_timestamp(args.window_start) if args.window_start else entries[0].timestamp
    end = parse_timestamp(args.window_end) if args.window_end else entries[-1].timestamp
    return start, end


def _now(entries, args):
    return parse_timestamp(args.now) if args.now else entries[-1].timestamp


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, help="path to the backup manifest")
    parser.add_argument("--drills", dest="drills_path", help="path to the restore drill log")
    parser.add_argument("--rpo-hours", type=_positive_int, default=24, help="declared RPO in hours (> 0)")
    parser.add_argument("--window-start", help="window start timestamp, ISO 8601 UTC")
    parser.add_argument("--window-end", help="window end timestamp, ISO 8601 UTC")
    parser.add_argument("--now", help="moment to measure drill freshness against, ISO 8601 UTC")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backupattest", description="Verify a backup regime can actually restore.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_chain = sub.add_parser("chain", help="assemble the recovery chain for a target time")
    _add_common(p_chain)
    p_chain.add_argument("--target", required=True, help="target time to recover to, ISO 8601 UTC")

    p_cov = sub.add_parser("coverage", help="run every check and print the findings report")
    _add_common(p_cov)

    p_drills = sub.add_parser("drills", help="check restore drill freshness only")
    _add_common(p_drills)

    sub.add_parser("version", help="print the version")
    return parser


def _load_drill_log(args):
    if not args.drills_path:
        raise DrillError("this command needs --drills")
    return load_drills(args.drills_path)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(f"backupattest {__version__}")
        return 0

    try:
        entries = load_manifest(args.manifest)
    except (ManifestError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not entries:
        print("error: manifest is empty", file=sys.stderr)
        return 2

    try:
        if args.command == "chain":
            target = parse_timestamp(args.target)
            chain = build_chain(entries, target)
            print("\n".join(render_chain(chain)))
            return 0 if chain.assembled else 1

        log = _load_drill_log(args)
        window_start, window_end = _window(entries, args)
        now = _now(entries, args)
        report = build_report(
            entries,
            log,
            timedelta(hours=args.rpo_hours),
            window_start,
            window_end,
            now,
        )

        if args.command == "coverage":
            print("\n".join(render_report(report)))
            return 0 if report.clean else 1

        if args.command == "drills":
            print("\n".join(render_drills(report)))
            return 0 if not (report.stale_drill or report.no_drill) else 1
    except (ManifestError, DrillError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
