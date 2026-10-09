# Automation and Discord

## Scheduled collection

`.github/workflows/update_jobs.yml` runs at 01:23 and 13:23 UTC every day and supports manual dispatch. In Madison, the local times are 20:23 / 08:23 during daylight saving time and 19:23 / 07:23 during standard time. GitHub scheduling may be delayed.

The workflow checks out the selected branch and previous snapshot, installs dependencies, runs tests, collects jobs, and commits changed `data/` files. Concurrent runs on the same branch are serialized. The automated author remains `jzikim` with `264001939+jzikim@users.noreply.github.com`.

`GITHUB_TOKEN` provides the data-commit permission; no personal access token is needed. Repository rules must allow these workflow commits. Scheduled execution uses the default branch, so a schedule change becomes active only after it is merged there.

## Discord behavior

Store the webhook URL as the Actions secret `DISCORD_WEBHOOK_URL`. Do not commit it to the repository.

- New target matches trigger alerts split to Discord's message limit.
- Every completed collection sends a separate summary, including runs with zero new targets.
- Missing webhook URLs and delivery failures do not stop collection or data commits.
- Summary delivery status is saved in `data/latest_run.json`.
- The initial complete baseline is quiet for new-job alerts, but still produces a run summary.
- Failed new-job alerts are not automatically retried after the snapshot advances.

## Validation

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

`.github/workflows/tests.yml` runs the suite on pull requests and pushes to `main`. It does not execute the collector, use the webhook, or modify data. The updater also runs the same suite before collection.

## Troubleshooting

| Symptom | Check |
|---|---|
| No new-job alert | Check `new_target_jobs.md`, baseline presence, the secret, and the collector log. Zero new jobs or an initial baseline is normal. |
| No summary | Check `discord_summary_status` in `latest_run.json` and the Actions log. |
| Partial results | Check `sources_succeeded` / `sources_total` and failing employer boards. The complete snapshot should remain intact. |
| No data commit | Check whether collection failed, tests failed, branch rules rejected the push, or no files changed. Completed collections normally update `latest_run.json`. |
| Schedule looks inactive | Confirm the workflow is on the default branch and inspect Actions; scheduled runs can be delayed. |

To run manually, use **Actions → Update internship jobs → Run workflow**. Local execution uses `python -m src.main`; use `--output` for a separate results folder when experimenting.
