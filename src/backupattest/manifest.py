"""Parse a backup manifest into typed entries.

The manifest is a line oriented text format so it diffs cleanly in git. Each
non blank, non comment line describes one backup:

    <kind> <id> <timestamp> <size> <digest> <verified> [parent]

Fields are separated by one or more spaces. Meaning:

- kind:       "full" or "incr"
- id:         a short identifier unique within the manifest
- timestamp:  ISO 8601 in UTC, seconds precision, e.g. 2026-08-01T00:00:00Z
- size:       bytes, a non negative integer
- digest:     the recorded content digest, e.g. sha256:abcd... (opaque here)
- verified:   "yes" or "no", whether the digest was ever checked against the bytes
- parent:     for incr only, the id of the backup it was taken against

Lines beginning with "#" are comments. Blank lines are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
