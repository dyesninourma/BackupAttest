# backupattest

<p align="right"><code>v0.1.0</code> | 29 tests, all passing | Python 3.11, stdlib only</p>

## Coverage of the bundled drill

The table below is filled from a real run of `backupattest coverage` against the
bundled `samples/`, using a 24 hour declared RPO and the sample window opening at
2026-08-01T00:00:00Z. Each row is one check and the finding it produced.

| Check                | Code | Result on the sample                                          |
| -------------------- | ---- | ------------------------------------------------------------- |
| Leading gap          | G001 | gap 2026-08-01T00:00:00Z to 2026-08-01T06:00:00Z              |
| Orphaned incremental | O001 | i-b3 at 2026-08-02T18:00:00Z, parent f-missing does not exist |
| Recovery objective   | R001 | achieved RPO 27h exceeds declared 24h                         |
| Unverified digest    | V001 | f-2 (sha256:5e5e5e5e) never checked                           |
| Stale restore drill  | D001 | last successful drill 2026-07-20T10:00:00Z outside interval   |

Five findings, so the command exits 1. The sample is built to fail every check on
purpose, so the output is a worked example of what each finding looks like.

## What this is

backupattest asks one blunt question about a backup regime: could you actually
restore, or do your jobs merely report success. Those are different questions. A
nightly job can report success for a year while the incrementals quietly point at
a full that was rotated away, or while no one has ever tried to restore from the
archive it produced.

Given a backup manifest (full and incremental entries with timestamps, sizes, and
digests) and a restore drill log, backupattest reconstructs the recovery chain for
any point in time and reports where the story falls apart:

- Gaps, spans of the timeline where no chain can be assembled at all.
- Orphaned incrementals, backups whose parent link never reaches a full.
- The achieved recovery point objective, measured from real timestamps, against
  the one you declared.
- Backups whose digest was recorded but never verified against the bytes.
- Whether a restore drill actually happened inside the declared interval.

It reads two text files, prints line oriented results, and sets an exit code. It
makes no network calls and has no dependencies beyond the Python standard library.

## The problem, concretely

You run full backups on a schedule and incrementals in between. Every job writes a
line to a manifest saying it finished: a timestamp, a size, a digest. Your
monitoring is green. The question that green does not answer is whether the pieces
still assemble into a restore.

Three things go wrong quietly:

1. An incremental records its parent as a full that has since been deleted by a
   retention policy. The incremental is intact, but it is useless: there is
   nothing to apply it on top of. Nothing in the job status shows this, because
   the job that wrote the incremental succeeded.

2. A full backup is late or missing. The window between the last usable recovery
   point and the next one grows past the recovery point objective you promised.
   Each individual job is fine. The regime as a whole has drifted out of spec.

3. Nobody has restored in months. The digests were recorded but never checked.
   The one time you need the archive, you discover the storage silently corrupted
   it, and the drill that would have caught this never ran.

backupattest is the check that turns those quiet failures into loud ones before
the incident does.

## Install

No install is required to run it from a clone. The package uses a src layout, so
put `src` on the path:

```
set PYTHONPATH=src
python -m backupattest version
```

To install it as a console script:

```
pip install .
backupattest version
```

## Usage

Four subcommands. All of them read the manifest, three of them also read the drill
log.

```
python -m backupattest chain    --manifest FILE --target TIME
python -m backupattest coverage  --manifest FILE --drills FILE [--rpo-hours N] [--window-start T] [--window-end T] [--now T]
python -m backupattest drills    --manifest FILE --drills FILE [--now T]
python -m backupattest version
```

Time inputs are explicit ISO 8601 UTC with a trailing Z, so output is
deterministic and does not depend on the wall clock. `--now` fixes the moment that
drill freshness is measured against and defaults to the newest backup timestamp.
The sample window defaults to the first and last backup timestamps.

### chain

Assemble the recovery chain for one target time and print each step.

Command:

```
python -m backupattest chain --manifest samples/manifest.txt --target 2026-08-02T12:00:00Z
```

Output:

```
target 2026-08-02T12:00:00Z
  base   f-1 full 2026-08-01T06:00:00Z
  apply  i-a1 incr 2026-08-01T18:00:00Z parent f-1
  apply  i-a2 incr 2026-08-02T06:00:00Z parent i-a1
  recovers to 2026-08-02T06:00:00Z
  steps 3
```

When the target lands before any full backup, no chain exists and the command
exits 1.

Command:

```
python -m backupattest chain --manifest samples/manifest.txt --target 2026-08-01T00:00:00Z
```

Output:

```
target 2026-08-01T00:00:00Z
  no chain: no full backup at or before the target
```

Notice that the orphaned incremental `i-b3` never appears in a chain. It sits in
the timeline between `i-a2` and `f-2`, but because it points at a full that does
not exist, the chain builder refuses to include it rather than pretending it
attaches to the nearest full.

### coverage

Run every check and print the report. This is the command you would wire into CI.

Command:

```
python -m backupattest coverage --manifest samples/manifest.txt --drills samples/drills.log --rpo-hours 24 --window-start 2026-08-01T00:00:00Z
```

Output:

```
rpo declared 24h achieved 27h MISS
unverified backups 1
last drill 2026-07-20T10:00:00Z stale

findings 5
  G001 gap 2026-08-01T00:00:00Z to 2026-08-01T06:00:00Z: window opens before the first full backup
  O001 orphan i-b3 at 2026-08-02T18:00:00Z: parent 'f-missing' does not exist
  R001 achieved RPO 27h exceeds declared 24h
  V001 unverified digest on f-2 (sha256:5e5e5e5e)
  D001 last successful drill 2026-07-20T10:00:00Z is outside the declared interval
```

### drills

Check only the restore drill freshness. Useful as a fast, standalone gate.

Command:

```
python -m backupattest drills --manifest samples/manifest.txt --drills samples/drills.log
```

Output:

```
last drill 2026-07-20T10:00:00Z stale
  D001 last successful drill 2026-07-20T10:00:00Z is outside the declared interval
```

### version

```
python -m backupattest version
```

Output:

```
backupattest 0.1.0
```

<p align="center">
  <img src="docs/assets/logo.svg" width="240"
       alt="The word backupattest, backup in slate and attest in teal, split at the boundary between the two words" />
</p>

<p align="center"><em>backup, the stored data. attest, the act of proving it restores.</em></p>

## Input format

Both inputs are line oriented text. Lines beginning with `#` are comments and
blank lines are ignored. The formats are a contract, described field by field
below.

### Manifest

Each data line is one backup:

```
<kind> <id> <timestamp> <size> <digest> <verified> [parent]
```

| Field     | Meaning                                                            |
| --------- | ------------------------------------------------------------------ |
| kind      | `full` or `incr`                                                   |
| id        | short identifier, unique within the manifest                       |
| timestamp | ISO 8601 UTC, seconds precision, trailing Z                        |
| size      | bytes, a non negative integer                                      |
| digest    | recorded content digest, opaque to this tool (for example sha256:) |
| verified  | `yes` or `no`, whether the digest was ever checked                 |
| parent    | for `incr` only, the id it was taken against                       |

A `full` line must not name a parent. An `incr` line must name one. Duplicate ids
are rejected, because the chain builder uses ids as unique keys.

