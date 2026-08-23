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
        failures.extend(bad)
        return f"FAIL no '--' inside XML comment: {'; '.join(bad)}"
    return "ok   no '--' inside XML comment"


def check_no_em_dash(failures: list[str]) -> str:
    """Check 4: no tracked text file contains U+2014, &#8212;, or &mdash;."""
    needles = ("\u2014", "&#8212;", "&mdash;")
    bad = []
    for path in _iter_text_files():
        text = _read(path)
        for needle in needles:
            if needle in text:
                rel = path.relative_to(ROOT)
                bad.append(f"{rel} ({needle!r})")
    if bad:
        failures.extend(bad)
        return f"FAIL no em dash family: {'; '.join(bad)}"
    return "ok   no em dash family"


def check_no_pandoc_image_attr(failures: list[str]) -> str:
    """Check 5: README has no pandoc style image attribute block."""
    readme = ROOT / "README.md"
    if not readme.is_file():
        return "ok   README has no pandoc image attribute (no README)"
    text = _read(readme)
    # Match `){` followed by width or height before the closing brace.
    pattern = re.compile(r"\)\{[^}]*(width|height)[^}]*\}")
    if pattern.search(text):
        failures.append("README.md pandoc image attribute block")
        return "FAIL README has no pandoc image attribute"
    return "ok   README has no pandoc image attribute"


def check_no_marketing(failures: list[str]) -> str:
    """Check 6: README contains none of the banned marketing terms."""
    readme = ROOT / "README.md"
    if not readme.is_file():
        return "ok   README free of marketing terms (no README)"
    lowered = _read(readme).lower()
    hits = [term for term in BANNED_MARKETING if term in lowered]
    if hits:
        failures.extend(f"marketing term {t!r}" for t in hits)
        return f"FAIL README free of marketing terms: {', '.join(hits)}"
    return "ok   README free of marketing terms"


def check_svg_accessibility(failures: list[str]) -> str:
    """Check 7: every SVG carries viewBox, role=img, a title, and a desc."""
    bad = []
    for svg in _iter_svgs():
        try:
            root = ET.fromstring(_read(svg))
        except ET.ParseError:
            bad.append(f"{svg.name}: does not parse")
            continue
        missing = []
        if root.get("viewBox") is None:
            missing.append("viewBox")
        if root.get("role") != "img":
            missing.append('role="img"')
        if root.find(f".//{SVG_NS}title") is None:
            missing.append("<title>")
        if root.find(f".//{SVG_NS}desc") is None:
            missing.append("<desc>")
        if missing:
            bad.append(f"{svg.name}: {', '.join(missing)}")
    if bad:
        failures.extend(bad)
        return f"FAIL svg accessibility metadata: {'; '.join(bad)}"
    return "ok   svg accessibility metadata"


def _text_extent(elem) -> tuple[float, float, float] | None:
    """Return (y, left, right) for one <text>, or None if not placeable."""
    x_attr = elem.get("x")
    y_attr = elem.get("y")
    size_attr = elem.get("font-size")
    if x_attr is None or y_attr is None or size_attr is None:
        return None
    try:
        x = float(x_attr)
        y = float(y_attr)
        size = float(size_attr)
    except ValueError:
        return None
    content = "".join(elem.itertext())
    em = _MONO_EM if _is_mono(elem.get("font-family", "")) else _SANS_EM
    width = len(content) * em * size
    anchor = elem.get("text-anchor", "start")
    if anchor == "middle":
        left = x - width / 2
    elif anchor == "end":
        left = x - width
    else:
        left = x
    return y, left, left + width


def check_no_label_overlap(failures: list[str]) -> str:
    """Check 8: no two labels sharing a baseline overlap."""
    bad = []
    for svg in _iter_svgs():
        try:
            root = ET.fromstring(_read(svg))
        except ET.ParseError:
            continue
        extents: dict[int, list[tuple[float, float, str]]] = {}
        for elem in root.iter(f"{SVG_NS}text"):
            ext = _text_extent(elem)
            if ext is None:
                continue
            y, left, right = ext
            label = "".join(elem.itertext()).strip()
            extents.setdefault(round(y), []).append((left, right, label))
        for baseline, group in extents.items():
            group.sort(key=lambda item: item[0])
            for (l1, r1, t1), (l2, r2, t2) in zip(group, group[1:]):
                if l2 < r1:
                    bad.append(f"{svg.name}: {t1!r} and {t2!r} overlap at y={baseline}")
    if bad:
        failures.extend(bad)
        return f"FAIL no overlapping labels: {'; '.join(bad)}"
    return "ok   no overlapping labels"


CHECKS = (
    check_svg_parses,
    check_no_banned_filters,
    check_no_double_hyphen_in_comment,
    check_no_em_dash,
    check_no_pandoc_image_attr,
    check_no_marketing,
    check_svg_accessibility,
    check_no_label_overlap,
)


def main() -> int:
    failed_checks = 0
    for check in CHECKS:
        failures: list[str] = []
        line = check(failures)
        print(line)
        if failures or line.startswith("FAIL"):
            failed_checks += 1
    total = len(CHECKS)
    print(f"verify: {total} checks, {failed_checks} failures")
    return 1 if failed_checks else 0


if __name__ == "__main__":
    sys.exit(main())
