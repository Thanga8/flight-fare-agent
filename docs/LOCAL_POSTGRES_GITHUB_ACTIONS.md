# Local app + GitHub Actions + PostgreSQL

## Architecture

The Flask UI runs only on the Windows PC at `127.0.0.1`. With no `DATABASE_URL`, it keeps using the existing SQLite file selected by `FLIGHT_DATABASE_PATH` (default `data/flights.db`). When `DATABASE_URL` is set, the web app, normal search, multi-leg history, price insights, monitoring dashboard, and GitHub Actions command all use the same PostgreSQL schema and data. Actions checks out the workflow's committed revision on the default branch and runs on an ephemeral GitHub-hosted Ubuntu runner; no database files or fare state are kept on that runner.

PostgreSQL uses a small DB-API compatibility wrapper around psycopg2 rather than an ORM rewrite. Schema initialization is repeatable and PostgreSQL startup/migrations are serialized with a transaction-scoped advisory lock. Monitor claims lock the selected job row with `FOR UPDATE`; SQLite retains `BEGIN IMMEDIATE`. Database errors shown by health/readiness surfaces are generic and contain no connection strings.

## Windows setup and daily use

From the repository folder in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally. Keep `DATABASE_URL` blank to use SQLite, or set it to the PostgreSQL connection string from Supabase. Do not paste secrets into chat or commit `.env`. SQLite remains available for local-only work and existing history.

For the owner-only monitor dashboard, set a private `MONITOR_OWNER_PASSWORD` (at least 12 characters) and a random `FLASK_SECRET_KEY` (at least 32 characters) in `.env`. Generate a key locally with:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep `SERPAPI_API_KEY` blank until you intentionally make a search. Telegram token/chat ID are optional and only needed if you choose to enable notifications on a monitor job.

Start the local UI (initializes/checks the configured database first):

```powershell
powershell -ExecutionPolicy Bypass -File .\run-local.ps1
```

Open `http://127.0.0.1:5000`. Stop with **Ctrl+C** in that same PowerShell window. The app binds only to loopback; do not change the host to `0.0.0.0`. The public, non-secret check is `http://127.0.0.1:5000/healthz`; the authenticated monitor readiness page also reports database and configuration presence. `.\.venv\Scripts\python.exe -m flask --app webapp db-ready` checks/initializes the database without searching fares.

For offline/mock validation, keep both database selectors empty and run the regression modules below. They use temporary SQLite databases and mocked provider responses; they do not perform paid fare searches or send notifications:

```powershell
$env:DATABASE_URL = ""
$env:TEST_POSTGRES_URL = ""
.\.venv\Scripts\python.exe -m unittest test_database_portability test_workflow_safety test_fare_monitor test_fare_change_detection test_provider_security test_multi_leg_persistence test_fare_history test_search_planner test_multi_leg test_scoring test_results test_historical_prioritization test_search_insights test_date_sampling test_webapp test_postgres_target_safety -q
```

The PostgreSQL integration suite is separate and destructive only to the explicitly named local disposable test database. It requires `TEST_POSTGRES_URL` to point to loopback and a database whose name starts with `test` or `disposable`; `DATABASE_URL` must remain blank. Do not point it at production or a shared environment.

## Supabase project and connection

1. Create a Supabase project yourself and choose the Free plan if it is offered and sufficient. Keep the database password private.
2. In the project dashboard, select **Connect** and copy a connection string; do not construct hostnames or usernames yourself.
3. For this app's short-lived connections, use the shared **Transaction pooler** string from that dialog when available. It is IPv4 compatible and appropriate for short-lived clients. The current driver does not enable prepared statements. Use **Session pooler** if you need session semantics, or direct connection only when your network supports the project's IP family; follow Supabase's connection guidance. Supabase can change plan limits and endpoint details.
4. Store the copied string in local `.env` as `DATABASE_URL=...`. Percent-encode reserved characters in the password if required by the copied URI. The same target string is later stored as a GitHub Actions secret, never in the repository.
5. With the dependencies installed, check it using `.\.venv\Scripts\python.exe -m flask --app webapp db-ready` from PowerShell. This initializes the additive application schema and confirms connectivity; it does not search flights. Using the interpreter path avoids requiring the virtual environment's `flask` command to be on `PATH`.

Supabase documents that its Free plan currently includes a 500 MB database allowance and may pause low-activity free projects after a week. Confirm current limits in the account dashboard before relying on it; no free tier is guaranteed permanent. Keep an independent backup/export because a free project is not a backup strategy.

## Back up and migrate SQLite history

Stop the Flask app before copying the SQLite file. Back it up without modifying it:

```powershell
Copy-Item .\data\flights.db .\data\flights.before-postgres.db
```

The legacy `reset_db.py` helper is SQLite-only and will refuse to run when `DATABASE_URL` selects PostgreSQL. It drops local search-history tables; do not run it as part of setup or migration.

After Supabase is created and local `DATABASE_URL` is configured, first run a read-only preflight against an **empty** PostgreSQL project:

```powershell
.\.venv\Scripts\python.exe -m flight_search.database.migrate_sqlite_to_postgres --source .\data\flights.db --dry-run
```

Review the table counts and confirm that the target is the intended empty project. Then migrate:

```powershell
.\.venv\Scripts\python.exe -m flight_search.database.migrate_sqlite_to_postgres --source .\data\flights.db
```

The tool requires the original `search_runs` and `flight_results` tables and accepts the monitoring and multi-leg tables as optional for older databases; missing optional tables are copied as empty. Present source tables are copied with their IDs. It checks source foreign keys, refuses a target containing rows in any public table, imports parent and child rows in one transaction, preserves SQLite `AUTOINCREMENT` high-water marks (including deleted IDs), and verifies per-table counts and key relationships. The source opens read-only and is never modified. A failed copy rolls back data rows; schema initialization may remain on the empty target, which is still safe for retry. Do not rerun after a successful migration: the now non-empty target is deliberately refused.

When counts and integrity pass, keep `DATABASE_URL` set and run `.\.venv\Scripts\python.exe -m flask --app webapp db-ready`, then start the UI and inspect search history, fare insights, monitor jobs, runs, and observations. The target must be empty before migration; there is no merge or overwrite option.

## GitHub Actions configuration and safety gate

The workflow is `.github/workflows/fare-monitor.yml`. Once it is on the repository default branch, its six-hour schedule is eligible to run. It uses `ubuntu-latest`, checks out the workflow revision (no fixed feature branch), serializes schedule/dispatch runs, has a 30-minute timeout, performs a DB readiness check, and then runs the same Flask CLI/database code as the local app. The top-level job condition requires repository variable `FARE_MONITOR_ENABLED` to equal the literal `true`; missing or false skips both scheduled and manually dispatched workflow runs. There is no workflow bypass input. The Python CLI independently fails closed unless the environment gate is true. This gate applies to automatic CLI/GitHub runs; an authenticated owner can still start a paid manual check from the local dashboard, and `/search` is independent of the monitoring gate.

In repository **Settings → Secrets and variables → Actions**, add these **secrets**:

- `DATABASE_URL` — the same Supabase connection string as local `.env`.
- `SERPAPI_API_KEY` — required only when the gate is deliberately enabled and a due job executes.
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` — optional, only for jobs with notifications enabled.

Add this **variable** and keep it `false` during setup:

- `FARE_MONITOR_ENABLED=false`

The workflow contains only read permission for repository contents. Database credentials are present only in the readiness and monitoring steps; provider and Telegram credentials are present only in the monitoring step. Never add credentials to `.env.example`, workflow text, test fixtures, logs, or commits. Scheduled events are only initiated from the workflow version on the default branch, so a reviewed PR to `main` is required before schedule activation. Merging this feature branch is not performed as part of this work.

## Budget, recovery, and costs

The configured per-run maximum remains 50 calls for web and monitor paths; multi-leg default is 50. New monitor jobs default to 6, and saved job budgets are not rewritten. Monitoring also has a global per-UTC-day ceiling, `MONITOR_MAX_DAILY_SERPAPI_BUDGET`, defaulting to 50 and capped at 50. Claims reserve each active job's entire budget under a cross-job database lock; completed jobs charge reported calls, and uncertain jobs charge the full reservation. A claim is skipped when the remaining daily allowance cannot cover its full per-run budget. This global ceiling covers monitor jobs only, not manual `/search` usage, other integrations, or spend outside this application's database. The GitHub job timeout is 30 minutes: 50 requests × the 30-second provider timeout is 25 minutes, with five minutes reserved for setup, database work, and notifications. There is no automatic provider retry loop. If a worker dies after claiming, exact call usage cannot be reconstructed because in-flight provider usage is not durably checkpointed. Lease recovery records the full reserved run budget as an `upper_bound`, sets remaining calls to zero, and holds the next attempt for the job interval. This may overstate actual usage, but will not silently treat an interrupted run as zero or reset the job budget.

- **Supabase:** Free limits, pausing, availability, backups, and plan terms can change. A shared database is required for cross-device persistence; there is no web host here.
- **GitHub Actions:** public-repository standard hosted minutes are free; private repositories have plan-specific included minutes/storage and overage billing may apply. Check repository billing and configure a spending budget. A six-hour schedule plus occasional manual dispatch is still Actions usage.
- **SerpApi:** calls can consume paid plan quota or credits. The current pricing page lists a free allowance and paid tiers, but your account's actual plan/quota controls. Keep monitoring disabled until intentionally activated and budgeted.
- **Telegram:** optional; this design adds no Telegram service charge of its own, but bot delivery requires your Telegram bot/chat setup.

No account, project, secret, deployment, migration, live search, or notification was created/performed in this implementation.

## Ordered personal checklist

1. Review this feature branch and open a PR targeting `main`; do not enable the gate as part of review.
2. Create a Supabase project and choose a supported connection string from **Connect**.
3. Back up `data/flights.db`, set local `DATABASE_URL` in ignored `.env`, and run the migration `--dry-run`.
4. Confirm the target is correct and empty; run the migration and compare the reported counts.
5. Run `.\.venv\Scripts\python.exe -m flask --app webapp db-ready`, start the local UI, and verify stored history and monitor data.
6. After the workflow change is on `main`, add the GitHub Actions secrets above and set `FARE_MONITOR_ENABLED=false`.
7. Confirm no credentials are tracked (`git status` and `git check-ignore .env`); leave monitoring disabled until you choose an activation window.
8. Check the Supabase, GitHub, and SerpApi account usage/limits before enabling scheduled jobs.

### Safe activation procedure

When ready: confirm `DATABASE_URL` and `SERPAPI_API_KEY` secrets, retain `FARE_MONITOR_ENABLED=false` while verifying the workflow appears on the default branch, then set the repository variable to `true`. In the authenticated local dashboard, enable only the intended paused job(s); verify each saved budget is within the 50-call per-run ceiling (new jobs default to 6). Use `workflow_dispatch` only after those checks. Inspect the Actions logs and monitor run status, then keep the gate true only while scheduled checks are desired. To stop all scheduled searches, set the variable back to `false`; separately disable any manual dashboard job. The gate does not block the owner-only **Run check now** action or API usage from the local `/search` page.

## Verification limits

Offline tests can validate SQL translation, SQLite behavior, migration preflight, routes, and disabled gates. A PostgreSQL server, Supabase project, GitHub Actions execution, credentials, real SerpApi request, and Telegram delivery are not available or exercised here. In particular, compatibility tests do not prove the live Supabase endpoint accepts this schema; perform `db-ready` and migration only in your own empty project.
