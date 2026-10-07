"""Shared job format and conservative text normalization."""

import re
from dataclasses import asdict, dataclass, field
from html import unescape
from html.parser import HTMLParser


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def clean_text(value):
    parser = PlainText()
    parser.feed(unescape(value or ""))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def matches(text, keywords):
    """Match whole phrases so 'intern' does not match 'international'."""
    return [word for word in keywords if re.search(
        r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, re.I
    )]


COUNTRY_ALIASES = {
    "Singapore": ["singapore", "sg"],
    "Australia": ["australia", "sydney", "melbourne", "brisbane", "perth", "adelaide"],
    "Canada": ["canada", "toronto", "vancouver", "montreal", "montréal", "ottawa", "waterloo", "calgary"],
    "United Arab Emirates": ["united arab emirates", "uae", "dubai", "abu dhabi"],
    "Qatar": ["qatar", "doha"],
    "Saudi Arabia": ["saudi arabia", "riyadh", "jeddah"],
    "South Korea": ["south korea", "republic of korea", "korea", "seoul", "busan", "incheon"],
    "Hong Kong": ["hong kong"],
    "Japan": ["japan", "tokyo", "osaka"],
    "United States": ["united states", "united states of america", "usa", "us", "u.s.", "new york", "san francisco", "chicago", "seattle", "boston", "los angeles", "austin", "san diego", "denver", "atlanta", "washington dc", "washington, dc", "palo alto", "mountain view", "san jose"],
    "United Kingdom": ["united kingdom", "uk", "u.k.", "london", "manchester", "edinburgh"],
    "Ireland": ["ireland", "dublin"],
    "India": ["india", "bengaluru", "bangalore", "mumbai"],
    "Germany": ["germany", "berlin"],
}


def extract_country(location):
    # Bare 'Korea' usually denotes South Korea, but North Korea must not match it.
    location = re.sub(r"\b(?:north korea|democratic people's republic of korea|dprk)\b", "", location or "", flags=re.I)
    countries = [name for name, aliases in COUNTRY_ALIASES.items() if matches(location, aliases)]
    # Preserve multi-country locations instead of arbitrarily selecting one.
    return "; ".join(countries)


def extract_sponsorship(description):
    sentences = re.split(r"(?<=[.!?;])\s+", description)
    relevant = [s.strip() for s in sentences if matches(s, [
        "sponsorship", "sponsor", "visa", "work authorization", "work authorisation",
        "work rights", "right to work", "authorized to work", "authorised to work",
        "legally eligible to work", "legally entitled to work",
    ])]
    return " ".join(relevant)


@dataclass
class Job:
    title: str = ""
    company: str = ""
    location: str = ""
    country: str = ""
    category: str = ""
    description: str = ""
    url: str = ""
    source: str = ""
    posted_date: str = ""
    deadline: str = ""
    internship: bool = False
    sponsorship_text: str = ""
    score: int = 0
    score_reasons: list[str] = field(default_factory=list)
    employment_type: str = ""

    def to_dict(self):
        return asdict(self)


def normalize(job, preferences):
    job.title = clean_text(job.title)
    job.description = clean_text(job.description)
    job.country = extract_country(job.location)
    # Title/type identify internships; descriptions often mention unrelated programs.
    job.internship = bool(matches(job.title + " " + job.employment_type,
                                  preferences["internship_keywords"]))
    job.sponsorship_text = extract_sponsorship(job.description)
    return job
