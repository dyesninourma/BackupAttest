# Sample fixtures

These files are hand authored test vectors, not captured production data. They
exist so the CLI has something real to run against and so the deliberate flaws
are reproducible.

## manifest.txt

A backup manifest covering the first week of August 2026, UTC. It contains two
full backups and five incrementals. Flaws built in on purpose:

- The window opens at 2026-08-01T00:00:00Z, but the first full is at 06:00, so
  there is a leading span with nothing to restore from (a gap, G001).
- `i-b3` names parent `f-missing`, which was never taken, so it is orphaned
  (O001).
- The interior span from `i-b3` (2026-08-02T18:00Z) to the next full `f-2`
  (2026-08-03T21:00Z) is 27 hours, wider than the declared 24 hour RPO (R001).
- `f-2` has `verified=no`, an unchecked digest (V001).

## drills.log

A restore drill log with a declared interval of 7 days. The last successful
drill is 2026-07-20, which is more than 7 days before the default `now` (the
newest backup, 2026-08-04T18:00:00Z), so the drill is stale on purpose (D001).
One drill in the middle failed, to show that failed drills do not count as
recent coverage.
