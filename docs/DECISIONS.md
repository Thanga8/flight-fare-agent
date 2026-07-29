# Flight Fare Agent — Architecture Decisions

This document records important decisions made during development.

The purpose is to prevent future development from repeatedly reconsidering decisions that have already been discussed and resolved.

---

# Decision 001 — Personal Project Scope

## Decision

The Flight Fare Agent is a personal travel tool.

## Rationale

The system is being built for one user's travel planning.

There is no current requirement for:

* Multi-user support.
* SaaS architecture.
* User authentication.
* Billing.
* Product analytics.
* Commercial deployment.

## Consequence

Prefer simple, maintainable architecture over enterprise infrastructure.

---

# Decision 002 — Primary Objective

## Decision

The primary objective is:

> Find the cheapest dates and flight combinations.

## Rationale

The user primarily wants to discover the best travel dates within a flexible date range.

Booking links and OTA resolution are secondary.

## Consequence

Search intelligence and date optimization take priority over booking integration.

---

# Decision 003 — SerpApi API Credits Are Limited

## Decision

Treat SerpApi credits as a scarce resource.

## Rationale

The project has already consumed a significant number of API credits.

The trip is approximately seven months away.

Continuous monitoring is therefore not currently appropriate.

## Consequence

Development must avoid unnecessary live API calls.

Prefer:

* Existing database.
* Existing JSON.
* Mock data.
* Fixtures.
* Unit tests.

Live API calls require explicit approval when they consume credits.

---

# Decision 004 — Current Stable Version Is v2.0.0

## Decision

`v2.0.0` is the current stable baseline.

## Included

* Flexible-date search.
* Adaptive search.
* Flight scoring.
* Historical fare intelligence.
* SQLite storage.
* Fare ratings.
* Fare recommendations.
* Previous-search price comparison.
* Telegram integration.
* `/search`.
* `/latest`.
* `/best`.
* `/history`.
* `/help`.

## Consequence

New work should preserve this baseline unless explicitly changing functionality.

---

# Decision 005 — Keep Historical Intelligence and Search-to-Search Comparison Separate

## Decision

Maintain two independent price-intelligence dimensions.

### Historical intelligence

Answers:

> Is the current fare good compared with historical observations?

### Search-to-search intelligence

Answers:

> Did the fare change since the previous search?

## Rationale

These answer different questions.

A fare can be:

* Historically cheap but unchanged since yesterday.
* Historically average but suddenly dropping.
* A new historical low and also cheaper than the previous search.

## Consequence

Do not merge these into one metric.

---

# Decision 006 — Use SQLite for Historical Data

## Decision

SQLite is the local historical data store.

## Rationale

The project is personal and does not require a production database.

SQLite provides:

* Local persistence.
* Simple deployment.
* No external database cost.
* Historical fare analysis.

## Consequence

Preserve historical observations.

Avoid destructive schema changes.

Use migrations where necessary.

---

# Decision 007 — Preserve the Existing Adaptive Search Architecture

## Decision

Keep the existing:

```text
Exploration
    ↓
Airport performance
    ↓
Adaptive search
```

architecture.

## Rationale

Adaptive search is one of the strongest parts of the system.

It already uses current-search results to direct remaining API budget.

## Consequence

Future improvements should enhance the planner rather than replace it unnecessarily.

---

# Decision 008 — Phase 3.2 Uses Historical Data to Prioritize Searches

## Decision

Historical data should influence which searches receive API budget priority.

## Rationale

The current adaptive system primarily learns from the current search.

Historical data can provide additional information before new searches begin.

## Consequence

The future planner should:

```text
Historical knowledge
        +
Current search knowledge
        ↓
Search priority
```

But historical knowledge must not completely eliminate exploration.

---

# Decision 009 — Do Not Blindly Trust Historical Data

## Decision

Historical search prioritization must retain exploration.

## Rationale

Historical data may be:

* Sparse.
* Old.
* Biased.
* Incomplete.
* Based on different market conditions.

A route that was historically expensive may become cheap tomorrow.

## Consequence

The search strategy should include:

* High-priority historical candidates.
* Medium-priority candidates.
* Exploration candidates.

---

# Decision 010 — Booking / OTA Intelligence Is Dropped

## Decision

Do not prioritize Phase 10 booking-token/OTA resolution.

## Rationale

The user's primary goal is finding cheap fares and dates.

Resolving `departure_token` into booking options may:

* Require additional API calls.
* Return limited providers.
* Return an OTA the user may not prefer.
* Still require manual price verification elsewhere.

The user is comfortable finding the booking source manually after discovering a good fare.

## Consequence

Booking integration is not part of the immediate roadmap.

---

# Decision 011 — departure_token Is Not the Primary Product Goal

## Decision

Do not make departure-token resolution a core feature.

## Rationale

The token is useful for itinerary/booking exploration but does not directly improve the primary goal of finding the cheapest travel dates.

## Consequence

Keep any experimental booking-token code isolated.

Do not complicate the core search pipeline with it.

---

# Decision 012 — FlightAPI.io Is Not Currently Useful for Russia

## Decision

Do not rely on FlightAPI.io as the primary verification source for the current Russia use case.

## Rationale

The project observed restrictions or lack of priced results for Russia-related routes.

## Consequence

Research alternative providers in Phase 6.

Do not spend additional credits on FlightAPI.io without a clear reason.

---

# Decision 013 — Phase 6 Is Research First

## Decision

Research Russia-compatible flight APIs before integrating another provider.

## Rationale

An additional API is useful only if it actually adds coverage.

The provider must be evaluated for:

* Russia domestic routes.
* International → Russia routes.
* Fare accuracy.
* Real-time data.
* Cost.
* Coverage.

## Consequence

Do not integrate an API simply because it offers a free trial.

---

# Decision 014 — Replace Original AI Prediction Phase

## Decision

The original broad AI fare-prediction concept is replaced by:

> Google Flights Price Insights / Market Intelligence research.

## Rationale

A large external fare dataset or market-level price intelligence may be more valuable than building a prediction model from a relatively small personal database.

## Consequence

Phase 7 should investigate legitimate access to market intelligence.

---

# Decision 015 — Do Not Assume Google Flights Price Insights API Exists

## Decision

Treat Google Flights Price Insights API access as unverified.

## Rationale

Google Flights has price-insight functionality, but this does not automatically mean there is a public API exposing the same information.

## Consequence

Before implementation:

* Verify official availability.
* Check legitimate API providers.
* Check terms.
* Check technical access.

Do not scrape or reverse-engineer undocumented interfaces.

---

# Decision 016 — Phase 7 Is a Later Intelligence Layer

## Decision

Phase 7 should come after sufficient historical data and search prioritization work.

## Rationale

The project should first improve its own data quality and API efficiency.

## Consequence

Phase 7 should eventually combine:

```text
Our historical data
        +
Current live search
        +
External market intelligence
```

---

# Decision 017 — Cloud Deployment Is Deferred

## Decision

Do not deploy the agent to the cloud yet.

## Rationale

The user does not currently need continuous monitoring.

The trip is approximately seven months away.

API credits are limited.

## Consequence

Phase 11 is deferred until:

* Travel date approaches.
* API strategy is finalized.
* Monitoring becomes worthwhile.

---

# Decision 018 — Cloud Deployment Must Solve PC-Off Alerts

## Decision

The main reason for Phase 11 is:

> Alerts must work even when the user's PC is turned off.

## Consequence

The future architecture should use:

```text
Cloud scheduler
        ↓
Fare search
        ↓
Historical evaluation
        ↓
Telegram notification
```

The user does not need a permanently running laptop.

---

# Decision 019 — Telegram Is a Presentation Layer

## Decision

Telegram should primarily present results.

## Rationale

Business logic belongs in:

* Search.
* Scoring.
* Evaluation.
* Historical intelligence.

## Consequence

Avoid duplicating fare calculations in `bot.py`.

The bot should consume structured results.

---

# Decision 020 — Fare Scoring and Fare Evaluation Are Different

## Decision

Keep scoring and historical fare evaluation separate.

### Scoring

Determines:

> Which current flight is the best overall option?

Uses:

* Price.
* Duration.
* Stops.
* Convenience.

### Fare evaluation

Determines:

> How good is the current fare compared with historical observations?

Uses:

* Historical average.
* Historical low.
* Exact-date history.
* Confidence.
* Fare rating.

## Consequence

Do not collapse these systems into one score.

Both are useful to the user.

---

# Decision 021 — Do Not Build High-Frequency Monitoring Now

## Decision

Do not implement six-hour or daily polling now.

## Rationale

The user explicitly wants to conserve API credits.

## Consequence

Manual `/search` remains the current approach.

Cloud alerts can be added later.

---

# Decision 022 — Open Jaw Is Experimental

## Decision

Open Jaw functionality should not complicate the stable round-trip system.

## Rationale

Open Jaw was explored experimentally but is not currently the primary requirement.

## Consequence

If retained, isolate it as an experimental search strategy.

Do not rewrite the stable search engine around it.

---

# Decision 023 — No Large Architectural Rewrite

## Decision

Prefer incremental improvements.

## Rationale

The project already has working:

* Search.
* Adaptive planning.
* Scoring.
* Historical data.
* Telegram.

A large rewrite introduces unnecessary risk.

## Consequence

When adding a feature:

1. Inspect existing implementation.
2. Identify the smallest integration point.
3. Reuse existing structures.
4. Add tests.
5. Preserve existing behavior.

---

# Decision 024 — Optimize for Cheapest Dates, Not Just Cheapest Flight

## Decision

The agent's primary output should identify the best date combinations.

## Rationale

The user's travel dates are flexible.

A slightly different date can produce a substantially cheaper fare.

## Consequence

The system should prioritize:

```text
Date combination discovery
        ↓
Fare comparison
        ↓
Best-date recommendation
```

rather than simply returning the cheapest fare for one fixed date.

---

# Decision 025 — API Budget Is Part of Search Intelligence

## Decision

API budget allocation is itself an optimization problem.

## Rationale

The agent has limited searches.

The best system is not necessarily the one that searches the most.

It is the one that gets the most useful information per API call.

## Consequence

Future search planning should consider:

```text
Expected information value
        +
Historical likelihood of cheap fares
        +
Exploration value
        +
API cost
```

---

# Current Agreed Development Order

The current order is:

```text
v2.0.0
    ↓
Phase 3.2
Historical Search Prioritization
    ↓
Phase 6
Russia-Compatible API Research
    ↓
Phase 7
Google Flights Price Insights /
Market Intelligence
    ↓
Phase 11
Cloud-Based Alerts
```

This order may change if new information materially changes the project's priorities.
