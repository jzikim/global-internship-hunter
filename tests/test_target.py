import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.models import extract_country
from src.target import build_target_jobs, save_target_jobs
from test_ranker import PREFERENCES, scored


class TargetTests(unittest.TestCase):
    def included(self, title, location):
        return bool(build_target_jobs([scored(title, location)], PREFERENCES)[0])

    def test_singapore_internship_included(self):
        self.assertTrue(self.included("Strategy Internship", "Singapore"))

    def test_canada_finance_intern_included(self):
        self.assertTrue(self.included("Finance Intern", "Canada"))

    def test_dubai_investment_intern_included(self):
        self.assertTrue(self.included("Investment Intern", "Dubai"))

    def test_us_strategy_internship_excluded(self):
        self.assertFalse(self.included("Strategy Internship", "New York, USA"))

    def test_hong_kong_internship_excluded(self):
        self.assertEqual(extract_country("Hong Kong"), "Hong Kong")
        self.assertFalse(self.included("Finance Internship", "Hong Kong"))

    def test_japan_internship_excluded(self):
        self.assertEqual(extract_country("Tokyo, Japan"), "Japan")
        self.assertFalse(self.included("Finance Internship", "Tokyo, Japan"))

    def test_singapore_senior_manager_excluded(self):
        self.assertFalse(self.included("Senior Strategy Manager", "Singapore"))

    def test_singapore_software_engineer_intern_excluded(self):
        self.assertFalse(self.included("Software Engineer Intern", "Singapore"))

    def test_technical_operations_engineer_excluded(self):
        self.assertFalse(self.included("Integration Reliability Engineer Intern, Technical Operations", "Singapore"))

    def test_past_internships_not_strong_entry_signal(self):
        job = scored("Data Analyst", "Canada", description="Requires 3 years of full-time experience exclusive of internships in Business Analyst roles.")
        self.assertEqual(build_target_jobs([job], PREFERENCES)[0], [])

    def test_unrelated_business_description_not_role_evidence(self):
        job = scored("PhD Research Intern", "Singapore", description="Our company has marketing, growth and finance teams.")
        self.assertEqual(build_target_jobs([job], PREFERENCES)[0], [])

    def test_seoul_with_missing_country(self):
        job = scored("Finance Intern", "Seoul")
        self.assertEqual(job.country, "South Korea")
        job.country = ""
        records, _ = build_target_jobs([job], PREFERENCES)
        self.assertEqual(records[0]["country"], "South Korea")

    def test_dubai_country_extraction(self):
        self.assertEqual(extract_country("Dubai"), "United Arab Emirates")

    def test_aliases_and_unknown_regions(self):
        for location, country in [("Korea", "South Korea"), ("Republic of Korea", "South Korea"),
                                  ("Sydney / Melbourne / Brisbane / Australia", "Australia"),
                                  ("Toronto / Vancouver / Canada", "Canada"), ("UAE", "United Arab Emirates"),
                                  ("Doha / Qatar", "Qatar"), ("Riyadh / Saudi Arabia", "Saudi Arabia"),
                                  ("Chicago", "United States"), ("London", "United Kingdom")]:
            self.assertEqual(extract_country(location), country)
        for location in ["Asia", "APAC", "Remote", "North Korea"]:
            self.assertEqual(extract_country(location), "")
            self.assertFalse(self.included("Finance Intern", location))

    def test_multi_country_projection_does_not_change_original(self):
        job = scored("Finance Intern", "Singapore; New York")
        original = job.to_dict()
        records, stats = build_target_jobs([job], PREFERENCES)
        self.assertEqual(records[0]["country"], "Singapore")
        self.assertEqual(stats["countries"]["Singapore"], 1)
        self.assertEqual(job.to_dict(), original)

    def test_export_sorting_and_funnel(self):
        jobs = [scored("Finance Intern", "Singapore"), scored("Finance Intern", "Canada"),
                scored("Software Engineer Intern", "Singapore"), scored("Business Analyst", "Canada")]
        for job in jobs:
            job.score = 80
        records, stats = build_target_jobs(jobs, PREFERENCES)
        self.assertEqual([r["country"] for r in records], ["Canada", "Singapore"])
        self.assertEqual((stats["saved"], stats["target_country"], stats["early_career"], stats["final"]), (4, 4, 3, 2))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            save_target_jobs(records, output)
            self.assertEqual(json.loads((output / "target_jobs.json").read_text(encoding="utf-8")), records)
            with (output / "target_jobs.csv").open(encoding="utf-8-sig", newline="") as file:
                self.assertEqual(len(list(csv.DictReader(file))), 2)
            self.assertEqual(sum(line.startswith("| ") for line in (output / "target_jobs.md").read_text(encoding="utf-8").splitlines()) - 1, 2)
