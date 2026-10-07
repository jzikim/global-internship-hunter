"""Deduplicate by canonical URL or company/title/location; choose richer/newer."""

import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalized(value):
    return re.sub(r"[^\w]+", " ", value.casefold()).strip()


def canonical_url(url):
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query)
             if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source", "tracking", "lever-source"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"),
                       urlencode(sorted(query)), ""))


def quality(job):
    try:
        posted = datetime.fromisoformat(job.posted_date.replace("Z", "+00:00"))
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        timestamp = posted.timestamp()
    except (ValueError, TypeError):
        timestamp = 0
    fields = job.to_dict()
    return (timestamp, sum(bool(value) for value in fields.values()), len(job.description))


def deduplicate(jobs):
    # Union connected duplicates: a URL and a tuple can bridge multiple versions.
    parent = list(range(len(jobs)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    for i, job in enumerate(jobs):
        keys = [("fields", normalized(job.company), normalized(job.title), normalized(job.location))]
        if job.url:
            keys.append(("url", canonical_url(job.url)))
        for key in keys:
            if key in seen:
                parent[root(i)] = root(seen[key])
            seen[key] = i
    groups = {}
    for i, job in enumerate(jobs):
        key = root(i)
        if key not in groups or quality(job) > quality(groups[key]):
            groups[key] = job
    return list(groups.values())
