# Global Internship Hunter

Small Python collector for an Economics / Data Science undergraduate at UW–Madison (graduating May or December 2028). Prioritizes business internships, summer opportunities, and seven preferred countries. Technical roles are secondary. No frontend, database, LLM, or paid API.

## Run (Python 3.11+)

```bash
cd global-internship-hunter
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
python -m unittest discover -s tests -v
```

Optional: `python -m src.main --config config/preferences.yaml --output data`

## Structure and output

- `src/main.py`: collect, normalize, deduplicate, filter, rank, export.
- `src/models.py`, `filters.py`, `ranker.py`, `dedupe.py`: plain deterministic logic.
- `src/sources/`: reusable HTTP base plus Greenhouse, Lever and Ashby adapters.
- `config/preferences.yaml`: roles, countries, keywords, scoring weights, penalties, boards, and HTTP settings.
- `tests/test_ranker.py`: scoring, deduplication, and source failure checks.
- `data/jobs.json`: all normalized fields for retained postings, including descriptions and score reasons.
- `data/jobs.csv`: score, company, title, location, country, publication date, sponsorship text, source, URL.
- `data/jobs.md`: ranked table with original posting links.

## Public sources

20 configured company boards (12 Greenhouse, 6 Lever, 2 Ashby). Coverage includes Stripe, Adyen, Agoda, Xendit, Careem, Geotab, AlphaSights, Guidepoint, Capco, Point72, Schonfeld, OKX, Spotify, Binance, Crypto.com, Lalamove, Fresha, Ninja Van, Wealthsimple and Airwallex. These are company boards, not global search engines. Only currently published postings returned by these endpoints are collected; internship availability changes over time.

API references: [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), [Ashby Public Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api).

To add another company on these platforms, add a `sources` entry with `type` (`greenhouse`, `lever`, or `ashby`), `company`, and its public `board` token. No Python edits are needed for another company. Board tokens are case-sensitive. For a new platform, subclass `JobSource` in a separate module, implement `fetch_jobs()` returning `Job` objects, and register it in `ADAPTERS` in `src/main.py`. The collector logs total and preferred-country counts before and after deduplication/filtering; multi-country jobs count once in each overall total.

## Ranking and limits

Score: role 40, country 20, internship/summer 15, business 15, data 5, explicit sponsorship support 5. Technical, senior, permanent, non-intern and clearly different-season roles receive penalties. Unknown dates and visa support do not exclude a posting. Senior titles and explicit minimum 3+ years requirements are filtered only when no internship/student title is present. Ambiguous and secondary technical jobs remain with lower scores.

Cities only help infer countries; no city has its own weight. Multi-country postings retain all inferred countries. Country inference and keyword matching are conservative heuristics. Visa sentences are copied as source evidence, with no legal or eligibility determination. Graduation requirements and exact internship dates need manual review; May 11–August 31 is a preference, not an automatic date exclusion. Missing publication dates stay blank (Greenhouse update timestamps are not publication dates).

Each run replaces the three ranked output files. Filtered experienced roles are not exported; JSON contains the complete normalized records for retained jobs. Partial source failure is logged and other boards continue. All-source failure preserves previous files and exits with status 1; partial results may be incomplete. There is no historical tracking.

## Automation and Discord

Push the project, including `data/target_jobs_snapshot.json`, to your GitHub repository's default branch. `.github/workflows/update_jobs.yml` runs daily at 13:23 UTC (about 08:23 CDT or 07:23 CST), tests the code, and commits changed `data/` files using `GITHUB_TOKEN`; no PAT is needed. Keep `data/` tracked so each run loads the previous snapshot. Repository rules must permit the workflow's direct commits.

Add your Discord webhook as **Settings → Secrets and variables → Actions → New repository secret → `DISCORD_WEBHOOK_URL`**. Only new target jobs trigger alerts; messages are split to Discord's limit. Missing webhook, zero new jobs, or delivery errors do not fail collection. The first run without a snapshot creates a quiet baseline. Manually run via **Actions → Update internship jobs → Run workflow**. Locally, `python -m src.main` works without a webhook; optionally set the same environment variable to enable alerts.

Every completed collection also sends a Discord run summary, even when there are zero new target jobs. `data/latest_run.json` records the execution time, counts, and summary delivery outcome, so every completed collection creates a data commit. Summary delivery failures are recorded and do not stop data commits. All-source failure still exits without replacing data or recording a completed run. New-job alerts remain separate and are not automatically retried after delivery failure.
