# Changelog

All notable changes to this project are recorded here.

## 0.1.0 - 2026-09-02

Initial release.

- Manifest parser for full and incremental backup entries with timestamps,
  sizes, digests, and a verified flag.
- Restore drill log parser with a declared drill interval.
- Recovery chain assembly for any target time, resolving parent links explicitly
  so a broken link surfaces as an orphan rather than a silently accepted chain.
- Achieved versus declared recovery point objective from real backup timestamps.
- Checks: gaps, orphaned incrementals, RPO miss, unverified digests, stale drill.
- CLI subcommands: chain, coverage, drills, version.
- Exit codes: 0 clean, 1 findings present, 2 usage error.
- Sample fixtures: a manifest with a leading gap and one orphan, and a drill log
  whose last successful drill is outside the declared interval.
- Coverage gaps data diagram and a wordmark logo.
