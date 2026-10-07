import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from src.main import main, ROOT
from src.models import Job
from src.notifications import build_payloads, message_length, notify_new_jobs

JOB = {"company": "Point72", "title": "Investment Summer Internship", "country": "Singapore",
       "location": "Singapore", "score": 95, "url": "https://example.org/jobs/1"}


class NotificationTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    @patch("src.notifications.requests.post")
    def test_missing_webhook_skips(self, post):
        self.assertEqual(notify_new_jobs([JOB]), 0)
        post.assert_not_called()

    @patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://example.org/webhook"})
    @patch("src.notifications.requests.post")
    def test_no_new_jobs_skips(self, post):
        self.assertEqual(notify_new_jobs([]), 0)
        post.assert_not_called()

    @patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://example.org/webhook"})
    @patch("src.notifications.requests.post")
    def test_new_jobs_payload_and_delivery(self, post):
        post.return_value = Mock()
        self.assertEqual(notify_new_jobs([JOB]), 1)
        payload = post.call_args.kwargs["json"]
        for value in ["1 New Internship Matches", "Point72", JOB["title"], "Singapore", "Score: 95", JOB["url"]]:
            self.assertIn(value, payload["content"])
        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        self.assertEqual(post.call_args.kwargs["timeout"], 15)

    def test_many_and_oversized_jobs_split_without_losing_information(self):
        jobs = [dict(JOB, title=f"Role {i}: " + "x" * 2500) for i in range(12)]
        payloads = build_payloads(jobs)
        self.assertGreater(len(payloads), 1)
        self.assertTrue(all(0 < len(payload["content"]) <= 2000 for payload in payloads))
        combined = "".join(payload["content"] for payload in payloads)
        for i in range(12):
            self.assertIn(f"Role {i}:", combined)
        self.assertEqual(combined.count(JOB["url"]), 12)

    def test_emoji_message_limit_and_content_preserved(self):
        payloads = build_payloads([dict(JOB, title="😀" * 3000)])
        self.assertTrue(all(message_length(payload["content"]) <= 2000 for payload in payloads))
        self.assertEqual(sum(payload["content"].count("😀") for payload in payloads), 3000)

    @patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://example.org/private-secret"})
    @patch("src.notifications.requests.post", side_effect=requests.RequestException("private-secret"))
    def test_failure_does_not_crash_pipeline_or_log_secret(self, post):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "target_jobs_snapshot.json").write_text("[]", encoding="utf-8")
            job = Job(title=JOB["title"], company=JOB["company"], location="Singapore",
                      country="Singapore", description="Business finance analytics internship.",
                      url=JOB["url"], internship=True)
            with patch("sys.argv", ["main", "--config", str(ROOT / "config/preferences.yaml"), "--output", str(output)]), \
                 patch("src.main.collect", return_value=([job], 20)), \
                 self.assertLogs("src.notifications", level="WARNING") as logs:
                self.assertEqual(main(), 0)
            post.assert_called_once()
            self.assertNotIn("private-secret", " ".join(logs.output))
            self.assertEqual(len(json.loads((output / "new_target_jobs.json").read_text(encoding="utf-8"))), 1)
            self.assertTrue((output / "target_jobs_snapshot.json").exists())
