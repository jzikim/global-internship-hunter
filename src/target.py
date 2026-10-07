"""Strict country, early-career and business-role shortlist; no AI calls."""

import csv
import json
import re
from dataclasses import replace

from src.filters import entry_signals, required_experience, senior_signals
from src.models import extract_country, matches


def strong_entry_signals(job, preferences):
    title_signals = matches(job.title, preferences["internship_keywords"] + preferences["student_keywords"])
    if title_signals or job.internship:
        return title_signals or ["internship employment type"]
    # Prior/excluded internships in experience requirements are not an entry offer.
    sentences = [sentence for sentence in re.split(r"(?<=[.!?;])\s+", job.description)
                 if not re.search(r"\b(?:excluding|exclusive of|previous|prior|past)\s+internships?\b", sentence, re.I)]
    return entry_signals(replace(job, description=" ".join(sentences)), preferences)


def build_target_jobs(jobs, preferences):
    allowed = set(preferences["preferred_countries"])
    settings = preferences["target_shortlist"]
    records = []
    stats = {"saved": len(jobs), "target_country": 0, "early_career": 0,
             "final": 0, "countries": {country: 0 for country in preferences["preferred_countries"]}}
    for job in jobs:
        countries = set((job.country or extract_country(job.location)).split("; ")) & allowed
        if not countries:
            continue
        stats["target_country"] += 1
        signals = strong_entry_signals(job, preferences)
        title_entry = matches(job.title, preferences["internship_keywords"] + preferences["student_keywords"])
        if not signals or required_experience(job) >= 3:
            continue
        # An explicit 'Product Manager Intern' is not a general manager vacancy.
        if senior_signals(job, preferences) and not (job.internship or title_entry):
            continue
        stats["early_career"] += 1
        if matches(job.title, preferences["excluded_roles"] + settings["excluded_roles"]):
            continue
        roles = matches(job.title + " " + job.category, settings["preferred_roles"])
        if not roles and matches(job.title, ["summer analyst", "summer associate"]):
            roles = ["summer analyst / associate"]
        generic_title = re.fullmatch(r"(?:2027\s+)?(?:summer\s+)?(?:intern(?:ship)?|student|graduate program|new grad)", job.title, re.I)
        if not roles and generic_title:
            roles = matches(job.description, settings["preferred_roles"])
        if not roles:
            continue
        record = job.to_dict()
        # A multi-location vacancy qualifies when it explicitly offers a target location.
        # Export only target-country options; preserve the original job and location.
        record["country"] = "; ".join(sorted(countries))
        record["early_career_signal"] = "; ".join(signals)
        record["role_category"] = "; ".join(roles)
        records.append(record)
        for country in countries:
            stats["countries"][country] += 1
    records.sort(key=lambda record: (-record["score"], record["country"],
                                     record["company"].casefold(), record["title"].casefold(), record["url"]))
    stats["final"] = len(records)
    return records, stats


def save_target_jobs(records, output, basename="target_jobs", heading="Strict target shortlist"):
    output.mkdir(parents=True, exist_ok=True)
    temp = output / f"{basename}.json.tmp"
    temp.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(output / f"{basename}.json")
    columns = ["score", "company", "title", "country", "location", "early_career_signal",
               "role_category", "source", "url"]
    temp = output / f"{basename}.csv.tmp"
    with temp.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    temp.replace(output / f"{basename}.csv")

    def cell(value):
        return str(value).replace("\n", " ").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]").replace("<", "&lt;").replace(">", "&gt;")

    lines = [f"# {heading}", "",
             "Target-country options only. Multi-country vacancies count once overall and once per eligible country; original locations remain visible.", "",
             "| Score | Company | Role | Country | Location | Early-career signal | Role category | Source | URL |",
             "|------:|---------|------|---------|----------|---------------------|---------------|--------|-----|"]
    for record in records:
        url = (record.get("url") or "").replace(" ", "%20").replace("(", "%28").replace(")", "%29").replace("|", "%7C")
        values = [cell(record.get(column, "")) if column != "url" else (f"[Posting]({url})" if url else "") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    temp = output / f"{basename}.md.tmp"
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temp.replace(output / f"{basename}.md")
