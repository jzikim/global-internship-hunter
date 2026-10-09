"""Run from any directory: python -m src.main --config ... --output ..."""

import argparse
import csv
import json
import logging
from pathlib import Path

import yaml

from src.dedupe import deduplicate
from src.changes import track_target_changes
from src.filters import keep_job
from src.models import normalize
from src.notifications import notify_new_jobs
from src.run_log import record_run
from src.ranker import rank_job
from src.shortlist import build_shortlist, save_shortlist
from src.target import build_target_jobs, save_target_jobs
from src.sources.ashby import AshbySource
from src.sources.greenhouse import GreenhouseSource
from src.sources.lever import LeverSource

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)
ADAPTERS = {"greenhouse": GreenhouseSource, "lever": LeverSource, "ashby": AshbySource}


def md_cell(value):
    return str(value).replace("\n", " ").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]").replace("<", "&lt;").replace(">", "&gt;")


def save_jobs(jobs, output):
    output.mkdir(parents=True, exist_ok=True)
    records = [job.to_dict() for job in jobs]
    # Temporary files prevent interrupted writes from leaving truncated data.
    temp = output / "jobs.json.tmp"
    temp.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(output / "jobs.json")
    columns = ["score", "company", "title", "location", "country", "posted_date", "sponsorship_text", "source", "url"]
    temp = output / "jobs.csv.tmp"
    with temp.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    temp.replace(output / "jobs.csv")
    lines = ["# Global Internship Hunter", "", "Ranked public postings. Verify dates and eligibility in the original posting.", "",
             "| Score | Company | Role | Country | Location | Source |",
             "|------:|---------|------|---------|----------|--------|"]
    for job in jobs:
        url = job.url.replace(" ", "%20").replace("(", "%28").replace(")", "%29").replace("|", "%7C")
        role = f"[{md_cell(job.title)}]({url})"
        lines.append(f"| {job.score} | {md_cell(job.company)} | {role} | {md_cell(job.country)} | {md_cell(job.location)} | {md_cell(job.source)} |")
    temp = output / "jobs.md.tmp"
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temp.replace(output / "jobs.md")


def collect(preferences):
    jobs = []
    succeeded = 0
    for settings in preferences["sources"]:
        source = None
        try:
            source = ADAPTERS[settings["type"]](settings["company"], settings["board"], preferences["http"])
            fetched = source.fetch_jobs()
            succeeded += 1
            logger.info("%s: fetched %d postings", settings["company"], len(fetched))
            for job in fetched:
                try:
                    jobs.append(normalize(job, preferences))
                except Exception:
                    logger.exception("Skipping malformed job from %s", settings["company"])
        except Exception:
            logger.exception("Source failed: %s; continuing", settings)
        finally:
            if source is not None:
                source.close()
    return jobs, succeeded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/preferences.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    with args.config.open(encoding="utf-8") as file:
        preferences = yaml.safe_load(file)
    jobs, succeeded = collect(preferences)
    if not succeeded:
        logger.error("All sources failed; previous output files preserved")
        return 1
    unique = deduplicate(jobs)
    ranked = [rank_job(job, preferences) for job in unique if keep_job(job, preferences)]
    ranked.sort(key=lambda job: (-job.score, job.company.casefold(), job.title.casefold(), job.url))
    save_jobs(ranked, args.output)
    shortlist = build_shortlist(ranked, preferences)
    save_shortlist(shortlist, args.output)
    logger.info("AI shortlist: %d candidates", len(shortlist))
    target_jobs, target_stats = build_target_jobs(ranked, preferences)
    save_target_jobs(target_jobs, args.output)
    new_target_jobs, closed_target_jobs = track_target_changes(
        target_jobs, args.output, complete=succeeded == len(preferences["sources"]))
    logger.info("Target changes: %d current; %d new; %d closed",
                len(target_jobs), len(new_target_jobs), len(closed_target_jobs))
    new_alert_messages = notify_new_jobs(new_target_jobs)
    record_run(args.output, fetched=len(jobs), retained=len(ranked),
               sources_succeeded=succeeded, sources_total=len(preferences["sources"]),
               targets=len(target_jobs), new=len(new_target_jobs), closed=len(closed_target_jobs),
               new_alert_messages=new_alert_messages)
    logger.info("Target funnel: %d saved; %d target-country; %d early-career; %d role-qualified",
                target_stats["saved"], target_stats["target_country"],
                target_stats["early_career"], target_stats["final"])
    for country, count in target_stats["countries"].items():
        logger.info("Target shortlist %s: %d", country, count)
    logger.info("Fetched %d; unique %d; retained %d; saved to %s", len(jobs), len(unique), len(ranked), args.output)
    preferred = set(preferences["preferred_countries"])
    logger.info("Preferred-country postings: %d fetched, %d unique, %d retained",
                sum(bool(set(job.country.split("; ")) & preferred) for job in jobs),
                sum(bool(set(job.country.split("; ")) & preferred) for job in unique),
                sum(bool(set(job.country.split("; ")) & preferred) for job in ranked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
