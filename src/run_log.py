"""Send a daily run summary and persist its delivery outcome for the data commit."""

import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

import requests

logger = logging.getLogger(__name__)


def record_run(output, *, fetched, retained, sources_succeeded, sources_total,
               targets, new, closed, new_alert_messages):
    record = {
        "run_id": os.environ.get("GITHUB_RUN_ID") or str(uuid4()),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "collection_status": "complete" if sources_succeeded == sources_total else "partial",
        "sources_succeeded": sources_succeeded,
        "sources_total": sources_total,
        "fetched": fetched,
        "retained": retained,
        "targets": targets,
        "new": new,
        "absent_from_target_list": closed,
        "new_alert_messages_sent": new_alert_messages,
        "discord_summary_status": "skipped_missing_webhook",
    }
    webhook = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    if webhook:
        content = (
            "Global Internship Hunter — Run log\n"
            f"UTC: {record['completed_at_utc']}\n"
            f"Collection: {record['collection_status']} ({sources_succeeded}/{sources_total} sources)\n"
            f"Fetched: {fetched} | Retained: {retained}\n"
            f"Target matches: {targets} | New: {new} | Absent: {closed}\n"
            f"New-job alert messages sent: {new_alert_messages}\n"
            "Run result is recorded in data/latest_run.json."
        )
        try:
            response = requests.post(webhook, json={"content": content, "allowed_mentions": {"parse": []}},
                                     params={"wait": "true"}, timeout=15)
            response.raise_for_status()
            record["discord_summary_status"] = "sent"
            logger.info("Discord run summary sent")
        except Exception as error:
            record["discord_summary_status"] = "failed"
            record["discord_error_type"] = type(error).__name__
            logger.warning("Discord run summary failed (%s); result recorded", type(error).__name__)
    else:
        logger.info("Discord run summary skipped: no webhook; result recorded")
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / "latest_run.json.tmp"
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output / "latest_run.json")
    return record
