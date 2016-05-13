#!/usr/bin/env python3
"""Quality gate for the backupattest repository.

Standard library only. Run from the project root:

    python scripts/verify.py

Exit 0 when every check passes, 1 when any check fails. One line per check is
printed, then a summary line such as `verify: 8 checks, 0 failures`.

Each check corresponds to a lesson recorded in _standards/LESSONS.md. The checks
are mechanical: they read the tracked text files and the SVG assets and refuse to
trust a human claim of correctness.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"

SVG_NS = "{http://www.w3.org/2000/svg}"

# Filters that signal decoration rather than an information graphic (lesson 9).
BANNED_FILTERS = ("feGaussianBlur", "feDropShadow", "feTurbulence")

# Marketing language that has no place in an honest README (lesson 7 and 8).
BANNED_MARKETING = (
    "blazing",
    "blazingly",
    "cutting-edge",
    "cutting edge",
    "state-of-the-art",
    "state of the art",
    "revolutionary",
    "game-changing",
    "game changing",
    "world-class",
    "world class",
    "seamless",
    "seamlessly",
    "effortless",
    "effortlessly",
    "supercharge",
    "next-generation",
    "next generation",
    "best-in-class",
    "unparalleled",
    "turnkey",
    "leverage the power",
)

# Text file suffixes that are worth scanning for the em dash family.
TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".svg",
    ".txt",
    ".log",
    ".toml",
    ".cff",
    ".yml",
    ".yaml",
    ".cfg",
    ".ini",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
}

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "build", "dist", ".eggs"}


def _iter_text_files():
    """Yield every tracked text file under the project root."""
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in path.parts):
            continue
        name = path.name
        if path.suffix in TEXT_SUFFIXES or name in {
            ".editorconfig",
            ".gitattributes",
            ".gitignore",
        }:
            yield path


def _iter_svgs():
    if not ASSETS.is_dir():
        return
    for path in sorted(ASSETS.rglob("*.svg")):
        if path.is_file():
            yield path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# Font width estimates, em per character, from LESSONS.md rule 4.
_SANS_EM = 0.58
_MONO_EM = 0.60


def _is_mono(font_family: str) -> bool:
    lowered = font_family.lower()
    return "mono" in lowered or "consolas" in lowered


def check_svg_parses(failures: list[str]) -> str:
    """Check 1: every SVG under docs/assets parses as XML."""
    bad = []
    for svg in _iter_svgs():
        try:
            ET.fromstring(_read(svg))
        except ET.ParseError as exc:
            bad.append(f"{svg.name}: {exc}")
    if bad:
        failures.extend(bad)
        return f"FAIL svg parses as XML: {'; '.join(bad)}"
    return "ok   svg parses as XML"


def check_no_banned_filters(failures: list[str]) -> str:
    """Check 2: no SVG uses a decorative filter primitive."""
    bad = []
    for svg in _iter_svgs():
        text = _read(svg)
        for banned in BANNED_FILTERS:
            if banned in text:
                bad.append(f"{svg.name}: {banned}")
    if bad:
        failures.extend(bad)
        return f"FAIL no decorative filters: {'; '.join(bad)}"
    return "ok   no decorative filters"


def check_no_double_hyphen_in_comment(failures: list[str]) -> str:
    """Check 3: no XML comment in any SVG contains the illegal `--` sequence."""
    comment = re.compile(r"<!--(.*?)-->", re.DOTALL)
    bad = []
    for svg in _iter_svgs():
        text = _read(svg)
        for body in comment.findall(text):
            if "--" in body:
                bad.append(svg.name)
                break
    if bad:
