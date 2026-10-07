import json
import tempfile
import unittest
from pathlib import Path

from src.changes import track_target_changes
from src.target import build_target_jobs
from test_ranker import PREFERENCES, scored


def record(url="https://example.org/jobs/1"):
    job = scored("Finance Intern", "Singapore")
    job.url = url
    return build_target_jobs([job], PREFERENCES)[0][0]


class ChangeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        self.job = record()

    def test_first_run_creates_baseline_not_new(self):
        self.assertEqual(track_target_changes([self.job], self.output), ([], []))
        self.assertEqual(json.loads((self.output / "target_jobs_snapshot.json").read_text(encoding="utf-8")), [self.job])
        for filename in ["new_target_jobs.json", "closed_target_jobs.json"]:
            self.assertEqual(json.loads((self.output / filename).read_text(encoding="utf-8")), [])
        self.assertTrue((self.output / "new_target_jobs.csv").exists())
        self.assertTrue((self.output / "new_target_jobs.md").exists())

    def test_existing_job_not_new_even_if_details_change(self):
        track_target_changes([self.job], self.output)
        updated = dict(self.job, title="Updated Finance Intern", score=99)
        self.assertEqual(track_target_changes([updated], self.output), ([], []))

    def test_new_url_is_new(self):
        track_target_changes([self.job], self.output)
        added = record("https://example.org/jobs/2")
        new, closed = track_target_changes([self.job, added], self.output)
        self.assertEqual(new, [added])
        self.assertEqual(closed, [])
        self.assertEqual(track_target_changes([self.job, added], self.output), ([], []))

    def test_missing_job_is_closed(self):
        track_target_changes([self.job], self.output)
        self.assertEqual(track_target_changes([], self.output), ([], [self.job]))
        self.assertEqual(json.loads((self.output / "closed_target_jobs.json").read_text(encoding="utf-8")), [self.job])

    def test_missing_url_uses_normalized_fields(self):
        original = record("")
        track_target_changes([original], self.output)
        updated = dict(original, company=original["company"].upper(), title="FINANCE  INTERN", location="singapore", url=None)
        self.assertEqual(track_target_changes([updated], self.output), ([], []))

    def test_tracking_parameters_do_not_create_new_identity(self):
        track_target_changes([self.job], self.output)
        updated = dict(self.job, url=self.job["url"] + "?utm_source=feed")
        self.assertEqual(track_target_changes([updated], self.output), ([], []))

    def test_partial_collection_does_not_close_or_replace_snapshot(self):
        track_target_changes([self.job], self.output)
        with self.assertLogs("src.changes", level="WARNING"):
            self.assertEqual(track_target_changes([], self.output, complete=False), ([], []))
        self.assertEqual(json.loads((self.output / "target_jobs_snapshot.json").read_text(encoding="utf-8")), [self.job])
