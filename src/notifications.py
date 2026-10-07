"""Optional, best-effort Discord alerts. Never log the secret webhook URL."""

import logging
import os

import requests

logger = logging.getLogger(__name__)
MESSAGE_LIMIT = 2000


def message_length(text):
    # Discord clients count astral characters (including emoji) as two units.
    return len(text.encode("utf-16-le")) // 2


def build_payloads(jobs):
    if not jobs:
        return []
    header = f"🚨 {len(jobs)} New Internship Matches\n\n"
    messages = []
    message = header
    for job in jobs:
        block = "\n".join([
            f"Company: {job.get('company') or ''}",
            f"Role: {job.get('title') or ''}",
            f"Country: {job.get('country') or ''}",
            f"Location: {job.get('location') or ''}",
            f"Score: {job.get('score', 0)}",
            f"URL: {job.get('url') or ''}",
        ]) + "\n\n---\n\n"
        # Keep ordinary jobs together; split even an unusually large single job.
        if message_length(message) + message_length(block) > MESSAGE_LIMIT and message != header:
            messages.append(message.rstrip())
            message = header
        while block:
            available = MESSAGE_LIMIT - message_length(message)
            piece = block.encode("utf-16-le")[:available * 2].decode("utf-16-le", errors="ignore")
            message += piece
            block = block[len(piece):]
            if block:
                messages.append(message.rstrip())
                message = header
    if message != header:
        messages.append(message.rstrip())
    return [{"content": content, "allowed_mentions": {"parse": []}} for content in messages]


def notify_new_jobs(jobs):
    webhook = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    if not webhook or not jobs:
        logger.info("Discord notification skipped: no webhook or no new target jobs")
        return 0
    sent = 0
    try:
        for payload in build_payloads(jobs):
            response = requests.post(webhook, json=payload, params={"wait": "true"}, timeout=15)
            response.raise_for_status()
            sent += 1
    except Exception as error:
        # requests error strings can contain webhook credentials; log type only.
        logger.warning("Discord notification failed (%s); job collection continues", type(error).__name__)
    return sent
