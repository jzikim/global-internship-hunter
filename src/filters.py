"""Exclude clear experienced roles while protecting student/entry-level signals."""

import re

from src.models import matches


def entry_signals(job, preferences):
    keywords = preferences["internship_keywords"] + preferences["student_keywords"]
    signals = matches(job.title, keywords)
    # A degree requirement alone is not evidence of a student opportunity.
    for sentence in re.split(r"(?<=[.!?;])\s+", job.description):
        if re.search(r"\b(?:mentor|manage|supervise|recruit|coach)(?:s|ing)?\s+(?:the\s+)?(?:interns|students)\b", sentence, re.I):
            continue
        description_keywords = [word for word in keywords if word not in {"undergraduate", "placement", "campus"}]
        if re.search(r"\bstudent (?:visas?|loans?)\b", sentence, re.I):
            description_keywords = [word for word in description_keywords if word not in {"student", "students"}]
        signals.extend(matches(sentence, description_keywords))
        signals.extend(matches(sentence, ["work placement", "student placement", "industrial placement", "campus hire", "campus program"]))
        if re.search(r"\b(?:undergraduate student|currently pursuing.{0,40}undergraduate)\b", sentence, re.I):
            signals.append("undergraduate student")
    return list(dict.fromkeys(signals))


def required_experience(job):
    """Find actual experience phrases, not a company's age or founding year."""
    text = job.title + " " + job.description
    numbers = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
               "eight": 8, "nine": 9, "ten": 10}
    pattern = (
        r"\b(\d+|three|four|five|six|seven|eight|nine|ten)"
        r"(?:\s*\+|\s*[-–]\s*\d+)?\s*(?:years?|yrs?)['’]?\s*"
        r"(?:of\s+)?(?:(?:relevant|related|professional|prior|previous|work|working|industry|hands-on|"
        r"commercial|practical|demonstrated|proven|progressive|sales|marketing|product|management|"
        r"project|software|engineering|consulting|finance|financial|accounting|business|analytics|operations)\s+){0,4}experience\b"
    )
    years = []
    for match in re.finditer(pattern, text, re.I):
        # Negated requirements must not turn into experience penalties.
        before = text[max(0, match.start() - 45):match.start()]
        after = text[match.end():match.end() + 30]
        if re.search(r"(?:do not require|does not require|not requiring|no requirement for)\s*$", before, re.I):
            continue
        if re.match(r"\s+(?:is\s+)?not required\b", after, re.I):
            continue
        value = match.group(1).lower()
        years.append(int(value) if value.isdigit() else numbers[value])
    # Also handle '5+ years in finance', without treating every number as experience.
    for match in re.finditer(
        r"\b(?:minimum(?: of)?|at least|requires?|must have)\s+(\d+)\+?\s+years?\s+(?:in|of)\s+(?!age\b)", text, re.I
    ):
        years.append(int(match.group(1)))
    return max(years, default=0)


def senior_signals(job, preferences):
    signals = matches(job.title, preferences["senior_keywords"])
    signals.extend(matches(job.title, ["managers", "directors", "specialists", "architects", "executives"]))
    if re.search(r"\bdirector(?=h/f\b|m/f\b|f/m\b)", job.title, re.I):
        signals.append("director")
    signals.extend(matches(job.description, ["experienced professional", "experienced hire"]))
    # Mentioning a manager/lead as a colleague does not make this role senior.
    for match in re.finditer(
        r"\b(?:this (?:role|position) is (?:a |an )?|we are (?:seeking|hiring|looking for) (?:a |an )?)"
        r"([^.!?;]{0,70})", job.description, re.I
    ):
        signals.extend(matches(match.group(1), preferences["senior_keywords"]))
    return list(dict.fromkeys(signals))


def permanent_role(job, preferences):
    if matches(job.title + " " + job.employment_type, preferences["permanent_keywords"]):
        return True
    return bool(re.search(
        r"\b(?:full[- ]time.{0,15}permanent|permanent.{0,15}full[- ]time|permanent (?:role|position|employment|contract))\b|"
        r"\b(?:this|the) (?:is a |role is |position is |role is a |position is a )"
        r"(?:full[- ]time|permanent)\b", job.description, re.I
    ))


def keep_job(job, preferences):
    if not job.title or not job.url:
        return False
    if job.internship or entry_signals(job, preferences):
        return True
    return not (senior_signals(job, preferences) or required_experience(job) >= 3
                or permanent_role(job, preferences))
