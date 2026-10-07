"""Ashby's public, unauthenticated job board endpoint."""

from src.models import Job
from src.sources.base import JobSource


COUNTRY_NAMES = {
    "SG": "Singapore", "SGP": "Singapore",
    "AU": "Australia", "AUS": "Australia",
    "CA": "Canada", "CAN": "Canada",
    "AE": "United Arab Emirates", "ARE": "United Arab Emirates",
    "QA": "Qatar", "QAT": "Qatar",
    "SA": "Saudi Arabia", "SAU": "Saudi Arabia",
    "KR": "South Korea", "KOR": "South Korea",
    "US": "United States", "USA": "United States",
    "GB": "United Kingdom", "GBR": "United Kingdom",
}


class AshbySource(JobSource):
    def fetch_jobs(self):
        data = self.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{self.board}")
        # Unlisted postings are intended only for people with a direct link.
        records = [record for record in data["jobs"] if record.get("isListed", True)]
        return self.parse_jobs(records, self.parse)

    def parse(self, record):
        locations = []
        primary = record.get("address") or {}
        addresses = [(record.get("location", ""), primary.get("postalAddress") or primary)]
        addresses.extend((item.get("location", ""), item.get("address") or {})
                         for item in record.get("secondaryLocations") or [])
        for location, address in addresses:
            country = address.get("addressCountry", "") or ""
            country = COUNTRY_NAMES.get(country.upper(), country)
            label = location
            if country and country.casefold() not in location.casefold():
                label = ", ".join(part for part in [location, country] if part)
            if label and label not in locations:
                locations.append(label)
        if record.get("isRemote"):
            locations.append("Remote")
        employment_type = record.get("employmentType", "")
        employment_type = {"FullTime": "full-time", "PartTime": "part-time"}.get(
            employment_type, employment_type)
        return Job(
            title=record["title"], company=self.company, location="; ".join(locations),
            category="; ".join(value for value in [record.get("department"), record.get("team")] if value),
            description=record.get("descriptionPlain") or record.get("descriptionHtml") or "",
            url=record["jobUrl"], source=f"Ashby:{self.board}",
            posted_date=record.get("publishedAt") or "", employment_type=employment_type,
        )
