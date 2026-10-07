import unittest
from unittest.mock import patch

from src.main import collect
from src.models import normalize
from src.sources.ashby import AshbySource
from test_ranker import PREFERENCES


class AshbyTests(unittest.TestCase):
    def setUp(self):
        self.source = AshbySource("Example", "Example", PREFERENCES["http"])
        self.addCleanup(self.source.close)

    def test_normalizes_public_posting_and_secondary_country(self):
        record = {
            "title": "Finance Placement", "location": "Remote",
            "address": {"postalAddress": {"addressCountry": "CA"}},
            "secondaryLocations": [{"location": "Singapore", "address": {"addressCountry": "SG"}}],
            "isRemote": True, "department": "Finance", "team": "Strategy",
            "descriptionHtml": "<p>Business analytics internship.</p>",
            "jobUrl": "https://jobs.ashbyhq.com/Example/123",
            "publishedAt": "2026-10-01T00:00:00Z", "employmentType": "Intern",
        }
        job = normalize(self.source.parse(record), PREFERENCES)
        self.assertEqual(job.country, "Singapore; Canada")
        self.assertTrue(job.internship)
        self.assertIn("Business analytics", job.description)
        self.assertEqual(job.posted_date, record["publishedAt"])

    def test_only_listed_and_valid_postings_returned(self):
        record = {"title": "Product Analyst", "location": "Toronto",
                  "jobUrl": "https://jobs.ashbyhq.com/Example/1", "employmentType": "FullTime"}
        with patch.object(self.source, "get_json", return_value={"jobs": [
            record, dict(record, isListed=False), {"title": "Malformed"},
        ]}), self.assertLogs("src.sources.base", level="ERROR"):
            jobs = self.source.fetch_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].employment_type, "full-time")

    def test_failed_board_does_not_stop_other_boards(self):
        preferences = dict(PREFERENCES, sources=[
            {"type": "ashby", "company": "Offline", "board": "offline"},
            {"type": "ashby", "company": "Online", "board": "online"},
        ])
        with patch.object(AshbySource, "fetch_jobs", side_effect=[
            RuntimeError("offline"), [self.source.parse({"title": "Finance Intern", "jobUrl": "https://example.org"})],
        ]), self.assertLogs("src.main", level="ERROR"):
            jobs, succeeded = collect(preferences)
        self.assertEqual(succeeded, 1)
        self.assertEqual(len(jobs), 1)
