from src.models import Job
from src.sources.base import JobSource


class GreenhouseSource(JobSource):
    def fetch_jobs(self):
        data = self.get_json(f"https://boards-api.greenhouse.io/v1/boards/{self.board}/jobs",
                             {"content": "true"})
        return self.parse_jobs(data["jobs"], self.parse)

    def parse(self, record):
        return Job(title=record["title"], company=self.company,
                   location=(record.get("location") or {}).get("name", ""),
                   category="; ".join(x["name"] for x in record.get("departments", [])),
                   description=record.get("content", ""), url=record["absolute_url"],
                   source=f"Greenhouse:{self.board}",
                   # updated_at is NOT a publication date.
                   posted_date=record.get("first_published", "") or "")
