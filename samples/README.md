# Sample fixtures

These files are hand authored test vectors, not captured production data. They
exist so the CLI has something real to run against and so the deliberate flaws
are reproducible.

## manifest.txt

A backup manifest covering the first week of August 2026, UTC. It contains two
full backups and five incrementals. Flaws built in on purpose:

- The window opens at 2026-08-01T00:00:00Z, but the first full is at 06:00, so
  there is a leading span with nothing to restore from (a gap, G001).
