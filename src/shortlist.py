"""Select and export a small rule-based candidate set for future AI review."""

import csv
import json

from src.filters import entry_signals, required_experience, senior_signals
from src.models import matches


def build_shortlist(jobs, preferences):
    settings = preferences["ai_shortlist"]
    preferred = set(preferences["preferred_countries"])
    candidates = []
    for job in jobs:
        signals = entry_signals(job, preferences)
        if not job.internship and not signals:
            continue
        # Technical skills in a business description are fine; technical roles are not.
        if matches(job.title, preferences["excluded_roles"] + settings["excluded_roles"]):
            continue
        title_entry = matches(job.title, preferences["internship_keywords"] + preferences["student_keywords"])
        if required_experience(job) >= 3:
            continue
        if senior_signals(job, preferences) and not (job.internship or title_entry):
            continue
        role = matches(job.title + " " + job.category, settings["preferred_roles"])
        summer_role = matches(job.title, ["summer analyst", "summer associate"])
        generic_entry = matches(job.title, preferences["internship_keywords"] + preferences["student_keywords"])
        if not (role or summer_role or (generic_entry and matches(job.description, settings["preferred_roles"]))):
            continue
        strength = 3 if job.internship or summer_role else 2 if title_entry else 1
        country_bonus = bool(set(job.country.split("; ")) & preferred)
        candidates.append((job, country_bonus, strength))
    # Preserve the deterministic score; country and entry strength break ties.
    candidates.sort(key=lambda item: (-item[0].score, -item[1], -item[2],
                                     item[0].company.casefold(), item[0].title.casefold(), item[0].url))
    limit = max(0, min(200, int(settings.get("max_candidates", 200))))
    return [job for job, _, _ in candidates[:limit]]


def save_shortlist(jobs, output):
    output.mkdir(parents=True, exist_ok=True)
    records = [job.to_dict() for job in jobs]
    temp = output / "ai_candidates.json.tmp"
    temp.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(output / "ai_candidates.json")
    columns = ["title", "company", "location", "country", "description", "url", "source",
               "posted_date", "sponsorship_text", "score", "score_reasons", "internship"]
    temp = output / "ai_candidates.csv.tmp"
    with temp.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(dict(record, score_reasons=json.dumps(record["score_reasons"], ensure_ascii=False)))
    temp.replace(output / "ai_candidates.csv")
    # Include complete descriptions in Markdown too; do not truncate AI evidence.
    def text(value):
        return str(value).replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|")

    lines = ["# AI review candidates", "", "Rule-based shortlist; score is the current deterministic score. No AI API was called.", ""]
    for job in jobs:
        url = job.url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
        title = text(job.title).replace("[", "\\[").replace("]", "\\]")
        lines.extend([f"## {job.score} — {text(job.company)}: [{title}]({url})", "",
                      f"Location: {text(job.location)} | Country: {text(job.country)}",
                      f"Source: {text(job.source)} | Posted: {text(job.posted_date)}",
                      f"Sponsorship: {text(job.sponsorship_text)}", "",
                      "Score reasons: " + text("; ".join(job.score_reasons)), "",
                      text(job.description), ""])
    temp = output / "ai_candidates.md.tmp"
    temp.write_text("\n".join(lines), encoding="utf-8")
    temp.replace(output / "ai_candidates.md")
