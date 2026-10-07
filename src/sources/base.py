"""Small reusable HTTP adapter with bounded retries."""

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class JobSource:
    def __init__(self, company, board, http):
        self.company = company
        self.board = board
        self.timeout = http["timeout"]
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": http["user_agent"], "Accept": "application/json"})
        retry = Retry(total=http["retries"], backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"], respect_retry_after_header=False)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get_json(self, url, params=None):
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def fetch_jobs(self):
        raise NotImplementedError

    def parse_jobs(self, records, parser):
        jobs = []
        for record in records:
            try:
                jobs.append(parser(record))
            except (TypeError, KeyError, ValueError, AttributeError):
                logger.exception("Skipping malformed posting from %s", self.company)
        return jobs

    def close(self):
        self.session.close()
