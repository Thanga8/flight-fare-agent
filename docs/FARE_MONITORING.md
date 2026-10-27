# Fare monitoring: implementation and deployment

## What is implemented

The owner-only Flask dashboard configures paused-by-default jobs, runs the existing two-leg search path, records run status, and stores fare observations in the existing SQLite database. Each returned itinerary compares to its latest successful observation; “not observed” is calculated against the immediately previous successful run. The identity uses the ordered provider flight segments (airport IDs, local departure/arrival times to the minute, carrier and flight number when available) plus the configured route, date window, nights, currency, and provider-default cabin/passenger context. Provider result IDs are not used. If segment endpoints and both a usable departure time and flight number are missing, that itinerary is omitted from fare comparison rather than guessed. The current provider query hardcodes INR and does not expose cabin or passenger controls; its default assumptions are treated as a comparison scope, not asserted as known passenger details.

Repeated itineraries in one run are deduplicated by identity, retaining the lowest total fare. Observations are appended transactionally and retained by run. Failed or partial searches do not become comparison baselines. A successful first observation is classified as new; subsequent successful observations are classified as decreased, increased, or no material change. Material INR changes require both thresholds: absolute difference >= `FARE_CHANGE_MIN_ABS_INR` (default 1000) and percentage difference >= `FARE_CHANGE_MIN_PERCENT` (default 3). Other currencies are suppressed from material-change classification; currencies are never converted. A fare absent from a run is labeled “not observed”, never treated as a price increase or proof of unavailability.

Telegram is only sent for successful runs when there is a new itinerary or a material change, avoiding repeated unchanged-fare messages. Delivery failures or skipped-notification reasons are stored separately from completed results. Run details and recent observations are visible in the dashboard. No extra provider requests are made for comparisons.

## Configuration by component

| Setting | Web service | Scheduler runner | Purpose |
|---|---:|---:|---|
| `SERPAPI_API_KEY` | Required for live/manual searches | Required for due searches | Provider credential; blank and common placeholder values are rejected before starting a search. Presence does not prove the key is accepted. |
| `FLASK_SECRET_KEY` | Required for monitoring login | Not required by CLI | Flask session signing; use at least 32 random characters. |
| `MONITOR_OWNER_PASSWORD` | Required for monitoring login | Not required by CLI | Single-owner dashboard access; use at least 12 characters. |
| `FLIGHT_DATABASE_PATH` | Same absolute path | Same absolute path | Persistent SQLite file shared by web process and runner. |
| `FARE_MONITOR_ENABLED` | Displayed as scheduler gate | Required and must be `true` | Workflow gate; CLI fails closed unless enabled. Leave unset/false until deployment is ready. |
| `MAX_WEB_SERPAPI_BUDGET` | Required for budget policy | Set to same ceiling | Hard-capped at 50 in code; set to 50 in both environments. This is a per-run maximum, not an account quota. |
| `MONITOR_MAX_SERPAPI_BUDGET` | Required for monitor ceiling | Set to same ceiling | Hard-capped at the overall ceiling of 50; set to 50 in both environments. New jobs default to 6 calls. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Needed for manual-run notifications | Needed for scheduled-run notifications | Optional pair. Missing values produce an explicit delivery status; never shown in readiness output. |
| `FARE_CHANGE_MIN_ABS_INR`, `FARE_CHANGE_MIN_PERCENT` | Optional | Optional | Thresholds must match on the web and runner when both can execute jobs; defaults are 1000 INR and 3%. |
| `COOKIE_SECURE` | `true` behind HTTPS | Not required | Enables Secure session cookies; local HTTP development can use `false`. HttpOnly and SameSite=Lax are enabled. |

`.env.example` contains only blank credentials and safe placeholders. Never commit `.env` or real values.

## Supported scheduler and database arrangement

The current database is SQLite. The supported arrangement for the current code is a Linux Flask web process and a self-hosted Linux GitHub Actions runner on the **same always-on host**, using the **same persistent local filesystem** and identical `FLIGHT_DATABASE_PATH`. The file must survive service restarts and deployments, and both process users need read/write access. The atomic database claim prevents two workers from claiming the same due job; SQLite serializes writers. Do not place this file on an arbitrary network filesystem or on separate web/runner hosts. This repository has no managed database or shared-volume deployment configured. If web and scheduler must run on separate hosts, a managed PostgreSQL adapter is the smallest appropriate next change; it is not implemented here.

The monitor workflow is `.github/workflows/fare-monitor.yml`, runs every six hours on a self-hosted runner labeled `linux` and `fare-monitor`, and invokes `flask --app webapp run-due-monitors`. It checks out `codex/multi-leg-itinerary-search`. **Repository default branch was inspected and is `main`; this PR targets `codex/multi-leg-itinerary-search`, and the workflow is not present on `main`. GitHub scheduled triggers only run from the default branch. Therefore merging PR #2 into its requested base will not activate the cron schedule.** Before using Actions scheduling, install this workflow file on `main` through a separately reviewed change (or merge/otherwise publish it through your normal process) after the target branch contains the feature. The workflow then checks out the feature base branch explicitly. Do not change the repository default branch for this feature. As an alternative, run the same Flask CLI command with a host scheduler on the persistent database host; that avoids the GitHub default-branch trigger constraint.

The workflow gate requires repository variable `FARE_MONITOR_ENABLED=true`. If unset or false, no job runs. The runner must be registered on the host that owns the local database volume, labeled `linux` and `fare-monitor`, and configured to run under a user with database access. A runner on a separate host cannot safely use a runner-local SQLite file.

The workflow intentionally checks out **`codex/multi-leg-itinerary-search`** regardless of which branch contains the workflow definition. That branch must contain the monitor CLI, database schema, and provider implementation. Any code intended for scheduled production execution must be merged/published to that exact branch first. Updating the workflow branch ref requires an explicit reviewed change; it is not automatically derived from the workflow's default-branch revision. The workflow is not installed on `main` by this PR, and this remediation does not publish it there.

## Production web process

There is no bundled deployment manifest. Use the production WSGI entry point `webapp:app`; do not use `python webapp.py` or Flask's development server in production. Install `requirements.txt`, then launch a single Gunicorn worker bound to loopback, for example:

```sh
gunicorn --bind 127.0.0.1:8000 --workers 1 --timeout 900 webapp:app
```

Place a TLS reverse proxy in front and run Gunicorn under a service manager such as systemd with the production environment injected by the service manager. Keep the DB on durable local disk outside the release checkout. A single worker is the supported initial setting for this SQLite app; the runner remains a separate process on the same host. Gunicorn's 900-second request limit is for web requests and is not the SerpApi request bound; provider calls are individually limited to 30 seconds.

## Budget and retry policy

The hard maximum is 50 for both the web search and monitoring budget. The code clamps `MAX_WEB_SERPAPI_BUDGET` to 50 even if configured higher, and monitoring is further limited by `MONITOR_MAX_SERPAPI_BUDGET`; set both to 50 in the web service and workflow. The workflow sets both explicitly. New monitor jobs still default to 6; each saved job is rejected before search if its per-run allowance exceeds either current ceiling. The provider wrapper also caps the actual live requests for that run. These are per-run limits, not a daily or account-wide quota; multiple due jobs can each consume their own allowance.

The workflow serializes its own invocations and does not cancel an active run. Each SerpApi SDK request has a 30-second timeout. If a process nevertheless dies while a run is recorded as running, the next claim after the 30-minute lease marks it failed, clears `running`, and defers `next_run_at` by the job interval. That claim returns without starting another search. Both scheduled and manual claims respect this recovery cooldown. A later scheduler invocation can retry only after the deferred due time. A completed provider request whose response was lost during termination may still have been charged; no local code can make the provider call and SQLite completion atomic.

## GitHub configuration checklist

In repository **Settings → Secrets and variables → Actions**:

**Variables**

- `FARE_MONITOR_ENABLED`: keep unset or set to `false` during setup; set to `true` only after the runner, persistent database path, and workflow's fixed checkout branch `codex/multi-leg-itinerary-search` are verified.
- `FLIGHT_DATABASE_PATH`: absolute path on the self-hosted Linux host, such as `/srv/flight-fare-agent/data/flights.db` (example only, not a required path).

**Secrets**

- `SERPAPI_API_KEY`
- `TELEGRAM_BOT_TOKEN` (optional unless Telegram is enabled on a job)
- `TELEGRAM_CHAT_ID` (optional unless Telegram is enabled on a job)

Separately configure the **web service process environment** with `SERPAPI_API_KEY`, `FLIGHT_DATABASE_PATH`, `FLASK_SECRET_KEY`, `MONITOR_OWNER_PASSWORD`, and the Telegram pair if manual-run notifications are wanted. Set both `MAX_WEB_SERPAPI_BUDGET=50` and `MONITOR_MAX_SERPAPI_BUDGET=50` there; the workflow sets both to 50 as well. GitHub secrets do not automatically configure a separate web host. Set the fare thresholds in both environments if overriding defaults.

## Enable, test, pause, and roll back

1. Deploy the web app and persistent volume on the chosen host. Confirm the web service and self-hosted runner use the same local absolute database path.
2. Add the owner/provider environment settings and GitHub variables/secrets above. Keep `FARE_MONITOR_ENABLED` false.
3. Sign in at `/monitor`. The readiness display and authenticated `GET /api/monitor/readiness` report configuration presence, database write reachability, and scheduler environment hints. They do not validate a SerpApi credential by making a request, verify a successful Telegram send, prove the workflow is on `main`, or prove that the mount is shared.
4. Save a paused job. Use **Run check now** for one deliberate live run after you have decided to spend the configured provider budget. A manual run uses up to the saved per-run limit. Inspect run status, fare observations, API use, and notification result.
5. To enable recurring checks, first publish the workflow on `main`, verify the self-hosted runner labels and shared local disk, then set `FARE_MONITOR_ENABLED=true`. Enable the job explicitly in the dashboard.
6. To pause, uncheck **Enabled** and save. To stop all automated searches immediately, set the repository variable false/unset and pause jobs. `run-due-monitors` checks the same gate before processing.
7. For rollback, disable the repository gate, pause jobs, then revert the workflow/application change through a reviewed PR. Observation and existing historical records are additive; do not delete the database to roll back.

Dashboard changes are protected by owner session authentication and CSRF tokens. `FLASK_SECRET_KEY` and `MONITOR_OWNER_PASSWORD` are required only for the monitoring control surface; unrelated public read-only/search routes retain their existing behavior. The readiness endpoint is owner-protected and reports statuses only, never values. Database failure blocks monitoring persistence; it is reported as unavailable. `MAX_WEB_SERPAPI_BUDGET` retains the existing project fail-fast validation if malformed; a malformed monitor-specific ceiling disables monitor budgets and appears in readiness without breaking unrelated imports.

## Verification status and limitations

- **Implemented:** dashboard control, protected state changes, run claims, due-job CLI, workflow file, append-only fare observations, comparisons, material thresholds, Telegram change summaries, readiness diagnostics, and budget/date rotation safeguards.
- **Locally tested:** offline unit tests with fake providers and mocked Telegram sender. No live provider or Telegram validation.
- **Deployment verified:** no. The workflow is not on default branch `main`; no runner, web host, persistent volume, repository secrets, or production settings have been configured or verified.
- GitHub schedule polling is every six hours, so a due job may start up to about six hours after its stored due instant.
- Date-pair rotation means different runs can search different non-anchor dates. A “not observed” label can therefore mean that a date pair was outside this run's sample.
- Current search parameters fix INR and rely on provider defaults for cabin/passengers. Those assumptions are included in identity scope; passenger/cabin selectors and currency conversion are not implemented.
- Telegram notification attempts are best-effort and failures are retained in run history. There is no transactional guarantee across SQLite and Telegram's external API.
- The first implementation is single-owner and relies on SQLite locking on one local persistent filesystem; it is not a multi-host or multi-user scheduler.

## Local tests

Run the relevant offline regression modules with `python -m unittest test_fare_monitor test_fare_change_detection test_multi_leg test_multi_leg_persistence test_webapp test_search_planner test_search_insights test_search_history test_scoring test_results test_historical_prioritization test_fare_history test_db_persistence -v`. All provider interactions are faked/mocked and Telegram is mocked. `test_flightapi_raw.py` is intentionally excluded because it performs a live provider request.
