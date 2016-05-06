"""Unit tests for backupattest, stdlib unittest only."""

import os
import unittest
from datetime import timedelta

from backupattest.chain import build_chain, find_gaps, find_orphans, latest_full_before
from backupattest.checks import build_report, drill_is_stale, unverified_backups
from backupattest.drills import DrillError, parse_drills
from backupattest.manifest import ManifestError, parse_manifest, parse_timestamp
from backupattest.rpo import achieved_rpo, format_duration
from backupattest.report import render_chain, render_report

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def _read(name):
    with open(os.path.join(SAMPLES, name), "r", encoding="utf-8") as handle:
        return handle.read()


class ManifestTests(unittest.TestCase):
    def test_parses_sample(self):
        entries = parse_manifest(_read("manifest.txt"))
        self.assertEqual(len(entries), 7)
        self.assertEqual(entries[0].id, "f-1")
        self.assertTrue(entries[0].is_full)

    def test_sorted_by_timestamp(self):
        entries = parse_manifest(_read("manifest.txt"))
        stamps = [e.timestamp for e in entries]
        self.assertEqual(stamps, sorted(stamps))

    def test_full_with_parent_rejected(self):
        with self.assertRaises(ManifestError):
            parse_manifest("full f-1 2026-08-01T00:00:00Z 10 sha256:aa yes p")

    def test_incr_without_parent_rejected(self):
        with self.assertRaises(ManifestError):
            parse_manifest("incr i-1 2026-08-01T00:00:00Z 10 sha256:aa yes")

    def test_bad_timestamp(self):
        with self.assertRaises(ManifestError):
            parse_timestamp("2026-08-01 00:00:00")

    def test_duplicate_id_rejected(self):
        text = (
            "full f-1 2026-08-01T00:00:00Z 10 sha256:aa yes\n"
            "full f-1 2026-08-02T00:00:00Z 10 sha256:bb yes\n"
        )
        with self.assertRaises(ManifestError):
            parse_manifest(text)

    def test_negative_size_rejected(self):
        with self.assertRaises(ManifestError):
            parse_manifest("full f-1 2026-08-01T00:00:00Z -1 sha256:aa yes")


class DrillTests(unittest.TestCase):
    def test_parses_sample(self):
        log = parse_drills(_read("drills.log"))
        self.assertEqual(log.interval_days, 7)
        self.assertEqual(len(log.drills), 3)

    def test_last_ok_ignores_failures(self):
        log = parse_drills(_read("drills.log"))
        self.assertIsNotNone(log.last_ok)
        self.assertEqual(log.last_ok.outcome, "ok")
        self.assertEqual(f"{log.last_ok.timestamp:%Y-%m-%d}", "2026-07-20")

    def test_missing_interval_rejected(self):
        with self.assertRaises(DrillError):
