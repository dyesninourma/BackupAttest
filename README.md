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

### Drill log

One directive declares the cadence, then each data line is one drill:

```
interval <days>
<timestamp> <backup_id> <outcome> [note...]
```

| Field     | Meaning                                          |
| --------- | ------------------------------------------------ |
| interval  | how often a drill is supposed to run, in days    |
| timestamp | ISO 8601 UTC, trailing Z, when the drill ran     |
| backup_id | the id that was restored                         |
| outcome   | `ok` if the restore verified, `fail` if it did not |
| note      | optional free text, kept verbatim                |

Only `ok` drills count as recent coverage. A `fail` drill is recorded but does not
reset the staleness clock.

## Output format

The `coverage` report is three summary lines, a blank line, then the findings.

| Line                | Meaning                                                       |
| ------------------- | ------------------------------------------------------------- |
| `rpo declared ...`  | declared objective, achieved worst gap, and `ok` or `MISS`    |
| `unverified backups N` | count of backups with `verified=no`                        |
| `last drill ...`    | timestamp of the last `ok` drill and `current` or `stale`     |
| `findings N`        | total findings, followed by one indented line each            |

Every finding carries a stable code so results are greppable and diff cleanly.

| Code | Finding                                                        |
| ---- | ------------------------------------------------------------- |
| G001 | a span of the window has no full backup to restore from       |
| O001 | an incremental whose parent chain never reaches a full        |
| R001 | achieved recovery point objective worse than declared         |
| V001 | a backup whose digest was never verified                      |
| D001 | last successful drill is older than the declared interval     |
| D002 | no successful restore drill exists at all                     |

## Exit codes

| Code | Meaning                                        |
| ---- | ---------------------------------------------- |
| 0    | clean, no findings, or a chain assembled       |
| 1    | findings present, or no chain could be built   |
| 2    | usage error, bad input, or a parse failure     |

## How the recovery chain is assembled

For a target time T the chain is built in two steps:

1. Find the base: the most recent `full` taken at or before T. If there is none,
   no chain exists and that is reported as a gap.
2. Walk the incrementals in timestamp order. An incremental joins the chain only
   when its parent is already rooted at the base, directly or through a run of
   incrementals that trace back to it, and it falls in the window after the base
   and at or before T.

The edge case that makes this harder than it looks is the broken middle link. The
naive approach is to assume each incremental attaches to whatever came before it.
That silently accepts a chain even when an incremental points at a parent that was
rotated away. backupattest resolves the parent id explicitly. If the link does not
trace back to a full, the incremental is reported as an orphan (O001) and left out
of every chain, rather than folded in as though it were sound.

When the data is ambiguous, the tool prefers to report a finding over guessing.
An incremental with a missing parent is never quietly reassigned to a nearby full.

## The achieved RPO, and why the window edges count

The achieved recovery point objective is the widest gap between consecutive
recoverable points inside the window. Every backup timestamp is a recoverable
point. The two window edges also count: the span from the window start to the
first backup, and from the last backup to the window end, are both real exposure
where a failure would lose everything back to the previous point.

In the sample, the widest interior gap runs from the orphaned incremental at
2026-08-02T18:00:00Z to the next full at 2026-08-03T21:00:00Z, which is 27 hours.
That exceeds the declared 24 hours, so R001 fires. The diagram below plots the
whole window with that gap marked.

![Timeline of the sample window from 2026-08-01T00:00Z to 2026-08-04T18:00Z, with
an amber band on the leading six hour gap, backup ticks labelled f-1 through i-c2,
a teal box around the widest 27 hour recovery gap, and the achieved RPO of 27h
printed against the declared 24h](docs/assets/coverage-gaps.svg)

## How to read the report and what to do

| Finding | What it means                              | What to do                                        |
| ------- | ------------------------------------------ | ------------------------------------------------- |
| G001    | a stretch of time has no restore point     | schedule a full to cover it, or shrink the window |
| O001    | an incremental is stranded from its full   | stop trusting it, take a fresh full and chain     |
| R001    | you lose more data than you promised       | increase backup frequency or relax the objective  |
| V001    | a digest was recorded but never checked    | verify the archive, then set the flag honestly    |
| D001    | nobody has restored recently               | run a real restore drill and log the outcome      |
| D002    | nobody has ever restored                   | run the first drill before you rely on any of it  |

A clean run prints `findings 0 (clean)` and exits 0.

## Design decisions

Text input, not a database or a backup tool API. The alternative was to talk to a
specific backup product and read its catalog directly. That would tie the tool to
one vendor and pull in a dependency and probably a network call. A line oriented
manifest is something any backup system can emit with a small export script, it
diffs cleanly in git, and it keeps the tool offline and vendor neutral. The cost
is that you write the exporter.

Explicit parent links, not positional adjacency. The alternative was to treat the
manifest as a simple ordered list and assume each incremental follows the previous
one. That is simpler and it is wrong in exactly the case that matters, the rotated
parent. Recording the parent id and resolving it is the whole point of the tool.

Window edges count toward the RPO. The alternative was to measure only interior
gaps between backups. But the exposure before the first backup and after the last
is real, and ignoring it would flatter the regime. Counting the edges makes the
achieved number honest, at the cost of requiring you to state the window.

Deterministic output with an injected `now`. The alternative was to read the
system clock for drill freshness. That would make output depend on when you ran
the tool, which breaks reproducibility and makes the tests flaky. Passing `now`
explicitly, defaulting to the newest backup, keeps runs byte identical.

Failed drills do not reset staleness. A drill that failed is evidence the restore
does not work, so counting it as recent coverage would be perverse. Only `ok`
drills move the clock.

## Repository layout

```
backupattest/
  README.md                     this file
  LICENSE                       MIT, holder "the backupattest authors", 2026
  CHANGELOG.md                  release notes
  pyproject.toml                setuptools, src layout, console script
  .gitignore
  src/backupattest/
    __init__.py                 package version
    __main__.py                 enables python -m backupattest
    cli.py                      argparse subcommands and exit codes
    manifest.py                 parse backup entries into typed records
    drills.py                   parse the restore drill log and interval
    chain.py                    assemble chains, find gaps and orphans
    rpo.py                      achieved versus declared recovery objective
    checks.py                   run every check and collect findings
    report.py                   render deterministic line oriented output
  tests/
    test_backupattest.py        unittest suite
  samples/
    manifest.txt                manifest with a gap and an orphan
    drills.log                  drill log whose last drill is stale
    README.md                   how each fixture was constructed
  docs/assets/
    logo.svg                    wordmark, split at the morpheme boundary
    coverage-gaps.svg           timeline diagram from the real run
```

## Glossary

- Full backup: a complete copy you can restore from on its own.
- Incremental: a copy of what changed since its parent, useless without the chain
  back to a full.
- Recovery chain: the full plus the ordered incrementals applied to reach a target
  state.
- Recovery point objective (RPO): the largest amount of data, in time, you accept
  losing.
- Gap: a span of the window with no full to restore from.
- Orphan: an incremental whose parent chain never reaches a full.
- Restore drill: a rehearsal where someone actually restores and confirms the
  result, rather than trusting the job status.

## Integration notes

The exit codes are the integration surface. In CI, run `coverage` and let a
non zero exit fail the job:

```
set PYTHONPATH=src
python -m backupattest coverage --manifest manifest.txt --drills drills.log --rpo-hours 24 --window-start 2026-08-01T00:00:00Z
```

Because output is line oriented and deterministic, two runs diff cleanly. Capture
the report to a file and `git diff` successive runs to see which finding appeared
or cleared between two points in time.

## Verification

The suite is stdlib `unittest`. Run it with the src layout on the path:

```
set PYTHONPATH=src
python -m unittest discover -s tests -v
```

The run reports `Ran 29 tests` and `OK`. The tests cover manifest and drill log
parsing including the rejection cases (bad timestamp, duplicate id, negative size,
full with a parent, incremental without one, missing interval, bad outcome), chain
assembly including the orphan exclusion and the no chain case, gap detection, the
achieved RPO measurement and its worst window endpoints, the drill staleness rule,
the full finding set on the sample, a clean run with no flaws, and deterministic
rendering.

## Limitations

- The digest is opaque. backupattest records whether a digest was verified, but it
  does not read the backup bytes or recompute the digest itself. It trusts the
  `verified` flag in the manifest to be set honestly.
- It does not restore anything. It reasons about whether a restore is possible from
  the metadata. A drill is still the only proof that the bytes are good.
- It does not fetch anything. Manifests and drill logs are files you provide; there
  is no connector to any backup product.
- One target at a time for `chain`. There is no batch mode that sweeps a range,
  though `coverage` reasons across the whole window.
- The window is a single interval. It does not model multiple protected systems
  with different objectives in one run.
- Timestamps are UTC only, seconds precision. There is no timezone handling and no
  sub second resolution.

## Roadmap

No dates are promised. Candidate work, in rough priority order:

- An optional mode that recomputes digests when given a path to the archives, so
  the `verified` flag can be audited rather than trusted.
- A batch `chain` that reports the recovery point for a list of targets.
- A machine readable output option alongside the line oriented text.

## License

MIT. See [LICENSE](LICENSE). Copyright 2026 the backupattest authors.
