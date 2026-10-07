"""Compare consecutive target snapshots without changing job selection or scores."""

import json
import logging

from src.dedupe import canonical_url, normalized
from src.target import save_target_jobs

logger = logging.getLogger(__name__)


def job_identity(record):
    url = (record.get("url") or "").strip()
    if url:
        return ("url", canonical_url(url))
    return ("fields", normalized(record.get("company") or ""),
            normalized(record.get("title") or ""), normalized(record.get("location") or ""))


def write_json(records, path):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def track_target_changes(current, output, complete=True):
    """First complete run creates baseline. Later runs replace the last snapshot.

    'Closed' means absent from the target list, not confirmed closed by an employer.
    Incomplete collection cannot establish absence, so preserve the snapshot.
    """
    output.mkdir(parents=True, exist_ok=True)
    snapshot = output / "target_jobs_snapshot.json"
    previous = None
    if snapshot.exists():
        previous = json.loads(snapshot.read_text(encoding="utf-8"))
        if not isinstance(previous, list) or not all(isinstance(record, dict) for record in previous):
            raise ValueError("Invalid target snapshot; previous snapshot preserved")
    new = []
    closed = []
    if previous is not None:
        previous_ids = {job_identity(record) for record in previous}
        current_ids = {job_identity(record) for record in current}
        new = [record for record in current if job_identity(record) not in previous_ids]
        if complete:
            closed = [record for record in previous if job_identity(record) not in current_ids]
    save_target_jobs(new, output, basename="new_target_jobs", heading="New target jobs")
    write_json(closed, output / "closed_target_jobs.json")
    # Update only after comparison and all change exports have succeeded.
    if complete:
        write_json(current, snapshot)
        if previous is None:
            logger.info("Created target baseline; new and closed lists are empty")
    else:
        logger.warning("Partial collection: snapshot preserved; no jobs marked closed")
    return new, closed
