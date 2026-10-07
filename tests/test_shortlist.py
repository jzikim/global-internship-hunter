import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.shortlist import build_shortlist, save_shortlist
from test_ranker import PREFERENCES, scored


class ShortlistTests(unittest.TestCase):
    def test_senior_full_time_excluded_even_with_program_boilerplate(self):
        job = scored("Senior Finance Manager", description="We run an internship program.", employment_type="full-time")
        self.assertEqual(build_shortlist([job], PREFERENCES), [])

    def test_summer_analyst_included(self):
        job = scored("Summer Analyst")
        self.assertEqual(build_shortlist([job], PREFERENCES), [job])

    def test_software_engineer_intern_excluded(self):
        for title in ["Software Engineer Intern", "Data Engineer Intern", "QA Engineer Intern", "Backend Intern"]:
            self.assertEqual(build_shortlist([scored(title)], PREFERENCES), [])

    def test_preferred_country_business_intern_included(self):
        job = scored("Business Operations Intern", location="Singapore")
        self.assertEqual(build_shortlist([job], PREFERENCES), [job])

    def test_maximum_200_and_score_order(self):
        jobs = [scored("Finance Intern") for _ in range(230)]
        for i, job in enumerate(jobs):
            job.score = i % 101
        shortlist = build_shortlist(jobs, PREFERENCES)
        self.assertEqual(len(shortlist), 200)
        self.assertEqual([job.score for job in shortlist], sorted((job.score for job in shortlist), reverse=True))

    def test_country_and_signal_strength_break_score_ties(self):
        other = scored("Finance Intern", location="London")
        preferred = scored("Finance Intern", location="Singapore")
        student = scored("Finance New Grad", location="Singapore")
        for job in [other, preferred, student]:
            job.score = 70
        self.assertEqual(build_shortlist([other, student, preferred], PREFERENCES), [preferred, student, other])

    def test_no_entry_signal_excluded(self):
        self.assertEqual(build_shortlist([scored("Business Analyst")], PREFERENCES), [])

    def test_full_descriptions_and_scores_preserved_in_exports(self):
        job = scored("Finance Intern", description="Business analytics. " + "Detailed role evidence. " * 1000)
        original = job.to_dict()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            save_shortlist(build_shortlist([job], PREFERENCES), output)
            self.assertEqual(json.loads((output / "ai_candidates.json").read_text(encoding="utf-8")), [original])
            with (output / "ai_candidates.csv").open(encoding="utf-8-sig", newline="") as file:
                record = next(csv.DictReader(file))
            self.assertEqual(record["description"], job.description)
            self.assertEqual(json.loads(record["score_reasons"]), job.score_reasons)
            self.assertIn(job.description, (output / "ai_candidates.md").read_text(encoding="utf-8"))
        self.assertEqual(job.to_dict(), original)
