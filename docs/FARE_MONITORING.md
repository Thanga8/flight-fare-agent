# Fare monitoring setup

The monitoring feature adds an owner-only Flask dashboard, SQLite schedule/run records, and a due-job CLI command that reuses `search_multi_leg_itineraries`. Schedules start paused. Frequency choices are daily, every 2 days (default), every 3 days, and weekly. The scheduler polls every six hours and claims only enabled jobs whose persisted UTC `next_run_at` is due; calculations use the configured IANA timezone (default `Asia/Kolkata`) and timezone-aware calendar-day increments.

## Initial setup checklist

1. Provision a host for the Flask webpage and a scheduler runner, and configure a durable SQLite volume accessible to both. SQLite requires one shared persistent filesystem and is suitable for this single-owner, single-worker deployment; do not use a runner-local database file.
2. Set `FLIGHT_DATABASE_PATH` to the durable database file path, `FLASK_SECRET_KEY` to a random secret, `MONITOR_OWNER_PASSWORD` to a strong owner password, and `SERPAPI_API_KEY` in the web host's environment. Never commit these values.
3. Set `MAX_WEB_SERPAPI_BUDGET` to the overall ceiling (currently 250 by default) and `MONITOR_MAX_SERPAPI_BUDGET` to the monitoring ceiling (12 by default). The web backend enforces the lower of both. A new job defaults to 6 provider requests; no job is enabled by default.
4. Configure Telegram optionally with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Enable notifications in a job only after testing credentials; failed sends are visible in the app logs but do not reverse a completed search.
5. On GitHub, set repository variable `FARE_MONITOR_ENABLED` to `true` only after confirming persistent storage is mounted and shared with the web host. The workflow runs a due-job sweep every six hours; GitHub Actions itself cannot mount arbitrary private host storage, so a self-hosted runner with the configured volume is required for this SQLite arrangement. Alternatively deploy the Flask CLI command `flask --app webapp run-due-monitors` as a scheduled process on the database host.
6. Sign in at `/monitor`, save a paused job, review its route, dates, frequency, and budget, then explicitly enable it. Use Run check now for an immediate run. Pause all jobs in the dashboard to disable future searches.

GitHub secrets/environment: `FLIGHT_DATABASE_PATH` (path on the self-hosted runner), `SERPAPI_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`. The web host separately needs `FLASK_SECRET_KEY` and `MONITOR_OWNER_PASSWORD`. GitHub hosted runners are ephemeral; setting a path there alone does not make SQLite durable. Production scheduling stays off unless `FARE_MONITOR_ENABLED=true`; the workflow is not operational until the durable shared database, self-hosted runner, web host, and secrets are configured and verified.

## Budget, coverage, and limitations

The search planner reserves up to two calls for combined multi-city checks before selecting date pairs. A hard provider-boundary gate prevents calls beyond the job budget, including combined verification. The endpoint and job budget are validated server-side. Two stable anchor dates are retained; the rest rotate deterministically using the persisted run cursor. Historical prices are not treated as new live results. Schedule interval changes recalculate the next due time immediately. The polling trigger's six-hour cadence means a job can start up to roughly six hours after its nominal due time.

The scheduler is a single-owner small deployment, not a multi-tenant scheduler. SQLite concurrency protection uses an atomic database claim; shared concurrent workers should use a locking-capable persistent filesystem. There is no notification test button or price-delta calculation in this first version. Telegram summaries include new run results and actual request use. No live SerpApi request or Telegram message should be used in tests.

## Local tests

Run `python -m unittest discover -v`. Provider interactions in tests use fakes/mocks. To inspect storage migrations locally, set `FLIGHT_DATABASE_PATH` to a disposable local file; existing historical SQLite records are preserved by additive table creation.
