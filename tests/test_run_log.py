import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from src.run_log import record_run


class RunLogTests(unittest.TestCase):
    def record(self, directory):
        return record_run(Path(directory), fetched=100, retained=20,
                          sources_succeeded=20, sources_total=20,
                          targets=7, new=0, closed=0, new_alert_messages=0)

    @patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://example.org/mock"}, clear=True)
    @patch("src.run_log.requests.post")
    def test_zero_new_jobs_still_sends_and_changes_record(self, post):
        post.return_value = Mock()
        with tempfile.TemporaryDirectory() as directory:
            first = self.record(directory)
            first_bytes = (Path(directory) / "latest_run.json").read_bytes()
            second = self.record(directory)
            self.assertEqual(post.call_count, 2)
            self.assertNotEqual(first_bytes, (Path(directory) / "latest_run.json").read_bytes())
            self.assertEqual(first["discord_summary_status"], "sent")
            self.assertEqual(second["new"], 0)
            self.assertIn("New: 0", post.call_args.kwargs["json"]["content"])
            self.assertEqual(post.call_args.kwargs["params"], {"wait": "true"})
            self.assertEqual(post.call_args.kwargs["json"]["allowed_mentions"], {"parse": []})

    @patch.dict("os.environ", {}, clear=True)
    @patch("src.run_log.requests.post")
    def test_missing_webhook_records_skip(self, post):
        with tempfile.TemporaryDirectory() as directory:
            record = self.record(directory)
            self.assertEqual(record["discord_summary_status"], "skipped_missing_webhook")
            post.assert_not_called()
            self.assertEqual(json.loads((Path(directory) / "latest_run.json").read_text(encoding="utf-8")), record)

    @patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://example.org/private-secret"}, clear=True)
    @patch("src.run_log.requests.post", side_effect=requests.RequestException("private-secret"))
    def test_failure_is_recorded_without_secret(self, post):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertLogs("src.run_log", level="WARNING") as logs:
                record = self.record(directory)
            self.assertEqual(record["discord_summary_status"], "failed")
            text = (Path(directory) / "latest_run.json").read_text(encoding="utf-8")
            self.assertNotIn("private-secret", text + " ".join(logs.output))
