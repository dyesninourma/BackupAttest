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
            parse_drills("2026-07-20T10:00:00Z f-1 ok\n")

    def test_bad_outcome_rejected(self):
        with self.assertRaises(DrillError):
            parse_drills("interval 7\n2026-07-20T10:00:00Z f-1 maybe\n")


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.entries = parse_manifest(_read("manifest.txt"))

    def test_latest_full_before(self):
        target = parse_timestamp("2026-08-02T12:00:00Z")
        base = latest_full_before(self.entries, target)
        self.assertEqual(base.id, "f-1")

    def test_chain_excludes_orphan(self):
        target = parse_timestamp("2026-08-03T00:00:00Z")
        chain = build_chain(self.entries, target)
        ids = [m.id for m in chain.members]
        self.assertIn("f-1", ids)
        self.assertIn("i-a1", ids)
        self.assertIn("i-a2", ids)
        self.assertNotIn("i-b3", ids)

    def test_no_chain_before_first_full(self):
        target = parse_timestamp("2026-08-01T00:00:00Z")
        chain = build_chain(self.entries, target)
        self.assertFalse(chain.assembled)
        self.assertIsNone(chain.recovery_point)

    def test_chain_recovery_point(self):
        target = parse_timestamp("2026-08-04T18:00:00Z")
        chain = build_chain(self.entries, target)
        self.assertEqual(chain.base.id, "f-2")
        self.assertEqual(f"{chain.recovery_point:%Y-%m-%dT%H:%M:%SZ}", "2026-08-04T18:00:00Z")

    def test_orphans_found(self):
        orphans = find_orphans(self.entries)
        ids = [o.entry.id for o in orphans]
        self.assertEqual(ids, ["i-b3"])
        self.assertIn("f-missing", orphans[0].reason)

    def test_leading_gap(self):
        start = parse_timestamp("2026-08-01T00:00:00Z")
        end = parse_timestamp("2026-08-04T18:00:00Z")
        gaps = find_gaps(self.entries, start, end)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(f"{gaps[0].start:%H:%M}", "00:00")
        self.assertEqual(f"{gaps[0].end:%H:%M}", "06:00")

    def test_no_gap_when_full_covers_start(self):
        start = parse_timestamp("2026-08-01T06:00:00Z")
        end = parse_timestamp("2026-08-04T18:00:00Z")
        self.assertEqual(find_gaps(self.entries, start, end), [])


class RpoTests(unittest.TestCase):
    def setUp(self):
        self.entries = parse_manifest(_read("manifest.txt"))
        self.start = parse_timestamp("2026-08-01T00:00:00Z")
        self.end = parse_timestamp("2026-08-04T18:00:00Z")

    def test_widest_gap_exceeds_declared(self):
        result = achieved_rpo(self.entries, timedelta(hours=24), self.start, self.end)
        self.assertFalse(result.meets)
        self.assertEqual(result.achieved, timedelta(hours=27))

    def test_meets_with_loose_declared(self):
        result = achieved_rpo(self.entries, timedelta(hours=48), self.start, self.end)
        self.assertTrue(result.meets)

    def test_worst_window_endpoints(self):
        result = achieved_rpo(self.entries, timedelta(hours=24), self.start, self.end)
        self.assertEqual(f"{result.worst_start:%Y-%m-%dT%H:%M:%SZ}", "2026-08-02T18:00:00Z")
        self.assertEqual(f"{result.worst_end:%Y-%m-%dT%H:%M:%SZ}", "2026-08-03T21:00:00Z")

    def test_format_duration(self):
        self.assertEqual(format_duration(timedelta(hours=27)), "27h")
        self.assertEqual(format_duration(timedelta(hours=1, minutes=30)), "1h30m")
        self.assertEqual(format_duration(timedelta(minutes=45)), "45m")


class ChecksTests(unittest.TestCase):
    def setUp(self):
        self.entries = parse_manifest(_read("manifest.txt"))
        self.log = parse_drills(_read("drills.log"))
        self.start = parse_timestamp("2026-08-01T00:00:00Z")
        self.end = parse_timestamp("2026-08-04T18:00:00Z")
        self.now = self.end

    def test_unverified(self):
        out = unverified_backups(self.entries)
        self.assertEqual([e.id for e in out], ["f-2"])

    def test_drill_stale(self):
        stale, last, none = drill_is_stale(self.log, self.now)
        self.assertTrue(stale)
        self.assertFalse(none)
        self.assertIsNotNone(last)

    def test_report_has_all_finding_codes(self):
        report = build_report(self.entries, self.log, timedelta(hours=24), self.start, self.end, self.now)
        codes = {f.code for f in report.findings()}
        self.assertEqual(codes, {"G001", "O001", "R001", "V001", "D001"})
        self.assertFalse(report.clean)

    def test_report_clean_when_no_flaws(self):
        text = (
            "full f-1 2026-08-01T00:00:00Z 10 sha256:aa yes\n"
            "incr i-1 2026-08-01T06:00:00Z 5 sha256:bb yes f-1\n"
        )
        entries = parse_manifest(text)
        log = parse_drills("interval 30\n2026-08-01T05:00:00Z f-1 ok\n")
        start = parse_timestamp("2026-08-01T00:00:00Z")
        end = parse_timestamp("2026-08-01T06:00:00Z")
        now = end
        report = build_report(entries, log, timedelta(hours=24), start, end, now)
        self.assertTrue(report.clean)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.entries = parse_manifest(_read("manifest.txt"))

    def test_render_chain_lines(self):
        target = parse_timestamp("2026-08-02T12:00:00Z")
        lines = render_chain(build_chain(self.entries, target))
        self.assertEqual(lines[0], "target 2026-08-02T12:00:00Z")
        self.assertTrue(any("base   f-1" in ln for ln in lines))

    def test_render_no_chain(self):
        target = parse_timestamp("2026-08-01T00:00:00Z")
        lines = render_chain(build_chain(self.entries, target))
        self.assertTrue(any("no chain" in ln for ln in lines))

    def test_deterministic_output(self):
        target = parse_timestamp("2026-08-04T18:00:00Z")
        first = render_chain(build_chain(self.entries, target))
        second = render_chain(build_chain(self.entries, target))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
