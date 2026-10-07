from datetime import datetime, timezone

from src.models import Job
from src.sources.base import JobSource


class LeverSource(JobSource):
    def fetch_jobs(self):
        records = self.get_json(f"https://api.lever.co/v0/postings/{self.board}", {"mode": "json"})
        return self.parse_jobs(records, self.parse)

    def parse(self, record):
        categories = record.get("categories") or {}
        description = " ".join([record.get("descriptionPlain") or record.get("description", ""),
                                record.get("additionalPlain") or record.get("additional", "")]
                               + [f"{x.get('text', '')}: {x.get('content', '')}"
                                  for x in record.get("lists", [])])
        created = record.get("createdAt")
        posted = datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if created else ""
        locations = categories.get("allLocations") or [categories.get("location", "")]
        return Job(title=record["text"], company=self.company,
                   location="; ".join(locations), category=categories.get("team", ""),
                   description=description, url=record["hostedUrl"],
                   source=f"Lever:{self.board}", posted_date=posted,
                   employment_type=categories.get("commitment", ""))
