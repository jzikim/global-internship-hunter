import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from src.dedupe import deduplicate
from src.filters import keep_job
from src.main import collect
from src.models import Job, normalize
from src.ranker import rank_job

with (Path(__file__).resolve().parents[1] / "config/preferences.yaml").open(encoding="utf-8") as file:
    PREFERENCES = yaml.safe_load(file)


def scored(title="Strategy Summer Internship", location="Singapore", **kwargs):
    job = Job(title=title, location=location, company="Example", url="https://example.org/job",
              description=kwargs.pop("description", "Business economics and analytics"), **kwargs)
    return rank_job(normalize(job, PREFERENCES), PREFERENCES)


class RankingTests(unittest.TestCase):
    def test_strategy_internship_high(self):
        job = scored()
        self.assertGreaterEqual(job.score, 90)
        self.assertTrue(job.score_reasons)

    def test_engineering_lower(self):
        self.assertLess(scored("Software Engineer Summer Internship").score, scored().score - 30)

    def test_preferred_country_bonus(self):
        self.assertEqual(scored(location="Singapore").score - scored(location="London").score, 20)

    def test_cities_have_equal_weight(self):
        self.assertEqual(scored(location="Sydney").score, scored(location="Melbourne").score)

    def test_sponsorship_never_excludes(self):
        job = scored(description="No sponsorship. Unrestricted work rights required.")
        self.assertTrue(keep_job(job, PREFERENCES))
        self.assertIn("No sponsorship", job.sponsorship_text)

    def test_negated_sponsorship_no_bonus(self):
        job = scored(description="Visa sponsorship is not available.")
        self.assertFalse(any(reason.startswith("+5 explicit visa") for reason in job.score_reasons))

    def test_unknown_dates_retained(self):
        job = scored("Business Analyst Intern")
        self.assertTrue(keep_job(job, PREFERENCES))

    def test_word_boundaries(self):
        job = scored("International Business Analyst")
        self.assertFalse(job.internship)

    def test_manager_low_score_and_filtered(self):
        manager = scored("Strategy Manager")
        self.assertLess(manager.score, scored().score - 30)
        self.assertIn("-30 senior/manager role", manager.score_reasons)
        self.assertFalse(keep_job(manager, PREFERENCES))

    def test_five_years_experience_penalty(self):
        job = scored("Business Analyst", description="Business analytics. 5+ years of experience required.")
        baseline = scored("Business Analyst", description="Business analytics.")
        self.assertEqual(baseline.score - job.score, 25)
        self.assertTrue(any(reason.startswith("-25 requires 5+ years") for reason in job.score_reasons))
        self.assertFalse(keep_job(job, PREFERENCES))

    def test_manager_intern_retained(self):
        job = scored("Product Manager Intern")
        self.assertTrue(keep_job(job, PREFERENCES))
        description_entry = scored("Product Manager", description="This internship is for a current student.")
        self.assertTrue(keep_job(description_entry, PREFERENCES))

    def test_summer_analyst_high(self):
        job = scored("Summer Analyst")
        self.assertGreaterEqual(job.score, 80)
        self.assertTrue(keep_job(job, PREFERENCES))

    def test_experience_range_and_negation(self):
        for phrase in ["3-5 years of relevant experience", "Minimum 4 years in finance", "Ten years of professional experience"]:
            self.assertFalse(keep_job(scored("Business Analyst", description=phrase), PREFERENCES))
        self.assertTrue(keep_job(scored("Business Analyst", description="5+ years of experience is not required."), PREFERENCES))

    def test_colleagues_and_degree_are_not_role_signals(self):
        junior = scored("Business Analyst", description="Work with senior managers. Business analytics.")
        self.assertTrue(keep_job(junior, PREFERENCES))
        experienced = scored("Senior Analyst", description="Undergraduate degree required. Mentor interns.")
        self.assertFalse(keep_job(experienced, PREFERENCES))

    def test_entry_signal_keeps_conflicting_experience_with_penalty(self):
        job = scored("Finance Intern", description="5+ years of experience preferred. Student opportunity.")
        self.assertTrue(keep_job(job, PREFERENCES))
        self.assertTrue(any(reason.startswith("-25 requires 5+ years") for reason in job.score_reasons))

    def test_unrelated_student_and_placement_wording_not_entry(self):
        for description in ["Salary placement varies by experience.", "We cannot support student visas.",
                            "Hiring, placement and promotion are equal opportunity."]:
            job = scored("Finance Manager", description=description)
            self.assertFalse(keep_job(job, PREFERENCES))

    def test_senior_filtered_but_technical_intern_kept(self):
        self.assertFalse(keep_job(scored("Senior Software Engineer"), PREFERENCES))
        self.assertTrue(keep_job(scored("Software Engineer Intern"), PREFERENCES))

    def test_duplicate_newer_and_richer(self):
        old = Job(company="Example Inc", title="Strategy Intern", location="Singapore",
                  url="https://example.org/1?utm_source=feed", posted_date="2026-01-01")
        new = Job(company="EXAMPLE INC", title="Strategy Intern", location="Singapore",
                  url="https://example.org/2", posted_date="2026-02-01", description="Details")
        self.assertEqual(deduplicate([old, new]), [new])
        rich = Job(**old.to_dict())
        rich.description = "More information"
        self.assertEqual(deduplicate([old, rich]), [rich])

    def test_canonical_url_and_bridge_duplicates(self):
        a = Job(company="A", title="Intern", location="Toronto", url="https://example.org/1")
        b = Job(company="B", title="Intern", location="Toronto", url="https://example.org/2")
        bridge = Job(company="A", title="Intern", location="Toronto", url="https://example.org/2?utm_source=x")
        self.assertEqual(len(deduplicate([a, b, bridge])), 1)

    def test_source_failure_isolated(self):
        # Keep this unit test isolated from the configured live company list.
        preferences = dict(PREFERENCES, sources=[
            {"type": "greenhouse", "company": "Stripe", "board": "stripe"},
            {"type": "lever", "company": "Spotify", "board": "spotify"},
        ])
        with patch("src.sources.greenhouse.GreenhouseSource.fetch_jobs", side_effect=RuntimeError("offline")), \
             patch("src.sources.lever.LeverSource.fetch_jobs", return_value=[Job(title="Strategy Intern", url="https://example.org")]), \
             self.assertLogs("src.main", level="ERROR"):
            jobs, succeeded = collect(preferences)
        self.assertEqual(succeeded, 1)
        self.assertEqual(len(jobs), 1)


if __name__ == "__main__":
    unittest.main()
