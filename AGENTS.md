# AGENTS.md

## Project

This repository contains a personal AI Flight Fare Agent.

The project's primary objective is:

> Find the cheapest flight dates and flight combinations within a flexible travel window while minimizing unnecessary flight-search API usage.

The project is currently optimized for a personal travel use case, not a commercial multi-user product.

---

## Current Stable Version

Current stable Git baseline:

`v2.0.0`

Treat `v2.0.0` as the stable baseline unless the user explicitly asks to change or refactor existing behavior.

New work should preserve all currently working functionality unless the task explicitly requires a breaking change.

---

## Primary User Goal

The user primarily wants to answer:

> "Within my flexible travel window, which dates and flight combinations are cheapest?"

The project is NOT primarily focused on:

* Finding a booking URL.
* Finding a specific OTA.
* Building a multi-user travel product.
* Continuous high-frequency monitoring.
* Predicting airline prices with an ML model.

These may be considered later, but they are not current priorities.

---

## Current Flight Search Context

The current primary use case is:

* Origin: HYD
* Destination: MOW
* Travel window: 2027-01-20 to 2027-02-13
* Trip duration: 5–6 days

These values are configuration examples, not hard-coded universal requirements.

The architecture should remain flexible enough to support other routes and date ranges.

---

## API Constraints

The project currently relies primarily on SerpApi / Google Flights search data.

SerpApi API credits are limited and must be treated as a valuable resource.

### Critical rule

DO NOT execute live SerpApi searches merely to inspect, test, debug, or experiment with code unless the user explicitly approves consuming API credits.

Prefer:

* Existing SQLite data.
* Existing raw JSON responses.
* Mock responses.
* Saved fixtures.
* Unit tests.
* Local test scripts.

When a live API call is genuinely necessary, explicitly state that it will consume API credits before executing it.

The user has previously consumed a significant portion of the available API credits and expects API usage to be minimized.

---

## Secrets

Never hard-code API keys or Telegram tokens.

Use environment variables and/or `.env`.

Expected examples include:

* `SERPAPI_API_KEY`
* `TELEGRAM_BOT_TOKEN`
* Other provider-specific keys

`.env` must never be committed to Git.

---

## Development Rules

Before changing code:

1. Inspect the relevant existing modules.
2. Understand how the current data flows through the system.
3. Reuse existing functions where possible.
4. Avoid duplicate logic.
5. Avoid unnecessary architectural rewrites.
6. Preserve the current working behavior.
7. Prefer the smallest safe change that solves the requested problem.

Do not assume a proposed feature is already implemented merely because it appears in the roadmap.

Clearly distinguish:

* Implemented
* Partially implemented
* Planned
* Experimental
* Rejected

---

## Testing Rules

Before making a live API request, prefer local testing.

Use:

* Existing SQLite database.
* Existing JSON responses.
* Mock provider responses.
* Unit tests.
* Standalone test scripts.

For provider-specific development, save representative raw API responses as fixtures when practical.

The test suite should not require live API access unless explicitly marked as an integration test.

---

## Search Architecture

The current search flow conceptually follows:

```text
Search configuration
        ↓
Flexible date combinations
        ↓
Initial exploration
        ↓
Airport/date performance evaluation
        ↓
Adaptive search
        ↓
Raw provider result
        ↓
Cheapest priced result extraction
        ↓
Normalization
        ↓
SQLite persistence
        ↓
Scoring
        ↓
Historical fare evaluation
        ↓
Recommendations
        ↓
Telegram presentation
```

Do not bypass the existing search architecture without a clear reason.

---

## Existing Intelligence

The system already supports:

* Flexible-date search.
* Multiple airport/route combinations.
* API budget allocation.
* Exploration and adaptive search.
* Flight scoring.
* Price scoring.
* Duration scoring.
* Stops scoring.
* Convenience scoring.
* Best Overall recommendation.
* Cheapest recommendation.
* Fastest recommendation.
* Best trip-duration recommendations.
* Historical fare storage.
* Historical fare evaluation.
* Historical low detection.
* Historical average comparison.
* Fare ratings.
* Fare scores.
* Previous-search price comparison.
* Telegram fare reporting.

Historical intelligence and search-to-search price movement are separate concepts and should not be accidentally merged.

---

## SQLite

SQLite is the project's local historical data store.

The database contains historical search runs and flight results.

The database is important because the project should become increasingly intelligent from its own accumulated observations.

Avoid destructive database migrations.

Do not delete historical data unless explicitly requested.

When changing the schema:

1. Explain the migration.
2. Preserve existing data.
3. Provide a safe migration path.
4. Test against the existing database.

---

## Telegram Bot

Telegram is currently the primary user interface.

Current commands include:

* `/start`
* `/help`
* `/search`
* `/latest`
* `/best`
* `/history`

The Telegram layer should remain relatively thin.

Business logic should preferably remain in the flight-search and historical-intelligence layers rather than being duplicated inside `bot.py`.

Telegram formatting should consume structured results rather than independently recalculating scores or fare evaluations.

---

## Important Design Principle

The project should follow:

```text
Provider
    ↓
Search / Normalization
    ↓
Historical Storage
    ↓
Scoring / Evaluation
    ↓
Recommendation
    ↓
Presentation
```

Do not put provider-specific logic into Telegram presentation code.

Do not put Telegram-specific formatting into the core search engine.

---

## Historical Search Prioritization

The next planned feature is Phase 3.2 after v2.0.0.

The intended behavior is:

```text
Historical observations
        ↓
Calculate route/airport/date priority
        ↓
Prioritize promising searches
        ↓
Retain exploration
        ↓
Execute limited API budget
        ↓
Save new observations
        ↓
Improve future prioritization
```

Historical data must influence search priority, but must NOT completely eliminate exploration.

The system must avoid becoming biased toward routes that were historically cheap while missing new opportunities.

---

## Current Roadmap Priority

The currently agreed roadmap is:

1. Phase 3.2 — Historical Search Prioritization.
2. Phase 7 — Google Flights Price Insights / Market Intelligence research.
3. Phase 6 — Research Russia-compatible flight APIs.
4. Phase 11 — Cloud-based Telegram alerts.

Phase 10 booking/OTA intelligence is currently dropped.

The original broad AI fare prediction concept has been replaced by investigating legitimate access to broader Google Flights price-insight or market-intelligence data.

---

## Phase 3.2 Scope

Phase 3.2 should focus ONLY on:

> Historical search prioritization to reduce exploration API cost.

Do not expand Phase 3.2 into:

* Continuous monitoring.
* Cloud deployment.
* AI prediction.
* Booking links.
* New provider integration.

The primary goal is better allocation of the existing API search budget.

---

## Phase 6 Scope

Phase 6 is research-first.

The goal is to find legitimate flight-data providers that add useful coverage for Russia-related routes.

Important routes include:

* International → Moscow.
* Moscow → Murmansk.
* Moscow → other Russian destinations.
* Russian domestic flights.

Before integration, evaluate:

* Russia domestic coverage.
* International → Russia coverage.
* Real-time fare availability.
* Price accuracy.
* Airline coverage.
* API cost.
* Free credits.
* Rate limits.
* Booking/OTA information.
* Python integration quality.

Do not spend API credits on a provider merely for experimentation.

Research first.

---

## Phase 7 Scope

Phase 7 is currently:

> Google Flights Price Insights / Market Intelligence research.

Do NOT assume a public Google Flights Price Insights API exists.

First determine whether there is a legitimate API or supported data source that provides useful price-insight information.

Do not build the project around:

* Scraping Google Flights.
* Reverse engineering undocumented endpoints.
* Violating terms of service.

If legitimate access exists, evaluate whether it can complement:

```text
Our historical observations
        +
Current SerpApi search
        +
Broader market-level price intelligence
```

The goal is to improve the answer to:

> "Is this fare actually cheap, or should I wait?"

---

## Phase 11 Scope

Phase 11 is specifically about:

> Alerts that work when the user's PC is turned off.

The eventual architecture may be:

```text
Cloud / Scheduled Job
        ↓
Flight search
        ↓
Historical comparison
        ↓
Threshold evaluation
        ↓
Telegram alert
```

Do not implement cloud deployment prematurely.

The user's trip is approximately seven months away and API credits are limited.

---

## Rejected / Deferred Features

Do not proactively implement the following unless the user changes the roadmap:

* High-frequency automatic monitoring.
* Six-hour polling.
* Full cloud deployment.
* Multi-user productization.
* Complex ML price prediction.
* Booking-token/OTA integration.
* Open Jaw as a primary production search path.
* Full automated travel-agent UI.

---

## Git and Release Discipline

The stable baseline is `v2.0.0`.

Treat tagged releases as stable checkpoints.

For significant features:

1. Create a feature branch.
2. Implement and test.
3. Commit changes.
4. Verify behavior.
5. Merge only after validation.
6. Tag a new version when appropriate.

Do not rewrite history or reset stable branches without explicit user approval.

---

## Communication Style

When explaining implementation changes:

* Explain WHY before HOW.
* State which files need modification.
* Prefer complete functions when the user is manually editing code.
* Avoid asking the user to blindly replace large sections of code unnecessarily.
* If a change affects multiple files, explain the dependency between them.
* Clearly identify whether a change is required or optional.

When the user asks for code, provide code that matches the existing architecture rather than inventing a new project structure.

---

## Final Principle

The project should continuously improve its ability to answer one question:

> "Given my travel window and limited API budget, what are the most promising dates and flight combinations to search, and is the resulting fare genuinely cheap?"

Optimize engineering decisions around that objective.
