"""Deterministic scoring. Visa text is evidence, never an eligibility decision."""

import re

from src.models import matches
from src.filters import entry_signals, permanent_role, required_experience, senior_signals


def rank_job(job, preferences):
    weights = preferences["scoring_weights"]
    penalties = preferences["penalties"]
    reasons = []
    total = 0

    def add(points, reason):
        nonlocal total
        points = int(points)
        if points:
            total += points
            reasons.append(f"{points:+d} {reason}")

    title = job.title.lower()
    text = title + " " + job.description.lower()
    business = matches(text, preferences["business_keywords"])
    roles = matches(title, preferences["preferred_roles"])
    engineering = matches(title, preferences["excluded_roles"])
    entry = entry_signals(job, preferences)
    if roles:
        pure_data = all(role in {"data science", "analytics"} for role in roles)
        fraction = 0.65 if pure_data and not business else 1
        add(weights["role"] * fraction, f"preferred role: {', '.join(roles)}")
    elif matches(job.category, preferences["preferred_roles"]):
        add(weights["role"] * 0.4, "relevant department; role uncertain")
    elif matches(title, ["summer analyst", "summer associate"]):
        add(weights["role"] * 0.75, "summer analyst / associate opportunity")
    if set(job.country.split("; ")) & set(preferences["preferred_countries"]):
        add(weights["country"], "preferred country (no city weighting)")
    summer = matches(title, preferences["summer_keywords"])
    if entry and not summer:
        # Description season helps only for confirmed internship roles.
        summer = matches(job.description, preferences["summer_keywords"])
    if job.internship or matches(title, ["summer analyst", "summer associate"]):
        add(weights["internship"] if summer else weights["internship"] * 0.8,
            "summer internship" if summer else "internship; exact dates may be unknown")
    elif entry:
        add(weights["internship"] * 0.8, f"student / early-career signal: {', '.join(entry)}")
    if business:
        add(weights["business"], "business / economics context")
    if matches(text, preferences["data_keywords"]):
        add(weights["data"], "data / analytics skills")
    visa = job.sponsorship_text.lower()
    negative = re.search(r"(?:no|without|not|unable|cannot|don't|do not|will not|does not).{0,65}(?:sponsor|visa)", visa)
    restriction = matches(visa, ["unrestricted work rights", "work authorization required", "work authorisation required"])
    positive = re.search(r"(?:sponsorship|visa support)\s+(?:is\s+)?(?:available|provided)|(?:provide|offer)(?:s)?\s+(?:visa\s+)?sponsorship", visa)
    if positive and not negative and not restriction:
        add(weights["sponsorship"], "explicit visa / sponsorship support; verify original terms")
    elif visa:
        reasons.append("+0 work authorization wording saved; eligibility not assessed")
    else:
        reasons.append("+0 visa support unclear")
    if engineering:
        add(-penalties["engineering"], "technical role is a secondary preference")
    if senior_signals(job, preferences):
        add(-penalties["senior"], "senior/manager role")
    experience = required_experience(job)
    if experience >= 3:
        add(-penalties["experience"], f"requires {experience}+ years experience (source wording; verify)")
    if not entry and not job.internship:
        if permanent_role(job, preferences):
            add(-penalties["permanent"], "explicit full-time / permanent non-intern role")
        add(-penalties["non_intern"], "internship not confirmed")
        add(-penalties["uncertain_entry"], "no clear student / entry-level signal")
    # Only explicit season in the title drives a mismatch. Do not invent dates.
    if job.internship and matches(title, ["winter", "fall", "autumn", "spring"] ) and not summer:
        add(-penalties["outside_availability"],
            f"season may fall outside {preferences['profile']['availability']['start']} to {preferences['profile']['availability']['end']}")
    job.score = max(0, min(100, total))
    if job.score != total:
        reasons.append(f"Score clamped to {job.score} (raw {total})")
    job.score_reasons = reasons
    return job
