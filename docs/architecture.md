# Architecture and scoring

## Pipeline

`src/main.py` coordinates these steps:

1. Read `config/preferences.yaml` and collect configured boards through `src/sources/`.
2. Normalize records with `models.py`; deduplicate job identities with `dedupe.py`.
3. Apply broad filtering in `filters.py`, then score and sort in `ranker.py`.
4. Export ranked jobs and rule-based review candidates in `shortlist.py`.
5. Build the strict country / early-career / business-role list in `target.py`.
6. Compare target identities with the previous complete snapshot in `changes.py`.
7. Send new-job alerts through `notifications.py`, then record the run and summary delivery outcome through `run_log.py`.

Collectors, selection rules, scoring, snapshot tracking, and notifications already have separate modules. Small modules remain at their existing paths to avoid breaking imports and the deployed command.

## Scores and selection

| Signal | Default weight |
|---|---:|
| Preferred role | 40 |
| Preferred country | 20 |
| Internship / summer | 15 |
| Business relevance | 15 |
| Data relevance | 5 |
| Explicit sponsorship support | 5 |

Technical, senior, permanent, non-intern, and clearly different-season roles receive penalties. Unknown dates or sponsorship information do not automatically exclude a posting. The broad list and stricter shortlists serve different purposes; a score alone does not determine target membership.

Cities help infer countries but do not receive separate weights. Multi-country vacancies count once overall and once per applicable country. Sponsorship sentences are copied as evidence, not interpreted as an eligibility guarantee. May 11–August 31 is a preference rather than a hard date exclusion; missing publication dates stay blank.

## Add a source

For another employer on an existing platform, add a `sources` entry containing `type`, `company`, and its public `board` token to the configuration. Board tokens are case-sensitive. For a new platform, implement `JobSource` in `src/sources/` and register the adapter in `src/main.py`.

API references: [Greenhouse](https://docs.greenhouse.io/job-board.html), [Lever](https://github.com/lever/postings-api), and [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api).

## Failure behavior

One failed source does not stop other collectors. Partial collection exports available results but preserves the last complete target snapshot and does not mark jobs absent. If every source fails, the command exits with status 1 and preserves previous outputs. Discord delivery failures are logged without exposing webhook URLs and do not fail collection.
