# Data files and snapshot lifecycle

All files under `data/` are intentional results or persistent state. JSON, CSV, and Markdown exports provide different views of the same collection.

| File family | Role |
|---|---|
| `jobs.json`, `jobs.csv`, `jobs.md` | Broad ranked results. JSON includes full descriptions and score reasons; CSV and Markdown provide compact views. |
| `ai_candidates.json`, `.csv`, `.md` | Up to 200 rule-based review candidates with full descriptions. No AI API is called. |
| `target_jobs.json`, `.csv`, `.md` | Strict preferred-country, early-career business shortlist, with role and career signals. |
| `new_target_jobs.json`, `.csv`, `.md` | Current target identities absent from the previous complete snapshot. |
| `closed_target_jobs.json` | Previous targets absent from the current complete list. This does not confirm employer closure. |
| `target_jobs_snapshot.json` | Persistent baseline used to recognize new and absent targets. Keep it tracked. |
| `latest_run.json` | Latest completed collection timestamp, source coverage, counts, and Discord summary outcome. |

## Snapshot lifecycle

The first complete run without a snapshot creates a quiet baseline with no new-job alerts. Later runs compare job identities using canonical posting URLs, falling back to normalized company, title, and location when a URL is missing.

A complete collection replaces the snapshot after comparison and change exports succeed. A partial collection can identify new jobs against the baseline, but preserves that baseline and produces no absent-job list. An invalid snapshot raises an error rather than overwriting its contents.

Deleting the snapshot resets new-job comparison. Moving it without updating the collector's output path has the same effect. This cleanup preserves all existing data paths and contents.

## Export writes

Writers create `*.tmp` files and replace the final files after each write finishes. These transient files are ignored by Git. Export families are refreshed in place rather than accumulated as dated copies. `latest_run.json` contains the latest completed run, not a full run history; Git commits and Actions runs provide historical context.
