# Fare monitoring

The owner-only dashboard manages paused-by-default monitor jobs. Successful runs retain fare observations and compare itinerary changes; failed or incomplete searches are not treated as successful baselines. Telegram notifications are optional and only attempted for successful runs with a new itinerary or material fare change.

The app now supports both local SQLite and shared PostgreSQL. `DATABASE_URL` takes precedence when configured; otherwise `FLIGHT_DATABASE_PATH` selects SQLite. The local Flask UI runs on loopback. GitHub Actions uses the same PostgreSQL database from its secret and a GitHub-hosted runner; it does not rely on runner disk.

## Safety and budgets

- Monitoring is disabled unless `FARE_MONITOR_ENABLED` is literally `true` in the GitHub repository variable and the workflow's job-level gate passes.
- `workflow_dispatch` has no bypass input. The CLI also checks the environment gate.
- Workflow runs are serialized and not cancelled while in progress. The 30-minute timeout covers 50 sequential 30-second requests plus five minutes of setup and database/notification overhead.
- PostgreSQL monitor claims lock the job row with `FOR UPDATE`; SQLite uses `BEGIN IMMEDIATE`.
- New monitor jobs default to 6 SerpApi requests. Existing saved budgets remain unchanged. The web, monitor, and multi-leg ceilings are capped at 50 calls per run. A global UTC-day monitor ceiling defaults to 50 (`MONITOR_MAX_DAILY_SERPAPI_BUDGET` may lower it); active jobs reserve their whole budget under a cross-job database lock. This does not include manual web searches or calls outside monitor jobs.
- Completed runs count reported calls. Interrupted or otherwise uncertain runs count the full reserved budget, are marked `upper_bound`, and hold retries for the job interval. Actual provider usage after abrupt termination cannot be reconstructed exactly.
- PostgreSQL uses both a global advisory transaction lock for daily reservations and `FOR UPDATE` on the job row; SQLite uses `BEGIN IMMEDIATE`.

## Workflow deployment

`.github/workflows/fare-monitor.yml` runs on `ubuntu-latest`, checks database readiness, and uses `DATABASE_URL`, `SERPAPI_API_KEY`, and optional Telegram secrets. Scheduled events only run the workflow revision on the repository default branch. Review and integrate the feature through a PR before expecting cron eligibility. Keep `FARE_MONITOR_ENABLED=false` until database migration, app verification, secrets, and job budgets are checked.

## Setup, migration, costs, and activation

Follow [Local app, PostgreSQL, and GitHub Actions setup](LOCAL_POSTGRES_GITHUB_ACTIONS.md) for Windows commands, Supabase setup, SQLite migration, backup/recovery, GitHub secrets, free-tier caveats, and the ordered safe activation checklist.
