# Flight Fare Agent — Roadmap

## Current Baseline

### `v2.0.0` — Stable

Status: ✅ Completed

The current stable release includes:

* Flexible-date flight search.
* Multiple airport/route combinations.
* Exploration search.
* Adaptive search.
* API budget allocation.
* Flight scoring.
* Price score.
* Duration score.
* Stops score.
* Convenience score.
* Best Overall recommendation.
* Cheapest recommendation.
* Fastest recommendation.
* Best trip-duration recommendations.
* SQLite search history.
* Historical fare evaluation.
* Historical average comparison.
* Historical low detection.
* Fare ratings.
* Fare scores.
* Previous-search price comparison.
* Telegram bot integration.
* `/start`.
* `/help`.
* `/search`.
* `/latest`.
* `/best`.
* `/history`.

---

# Priority Roadmap

```text
v2.0.0
   │
   ▼
Phase 3.2
Historical Search Prioritization
   │
   ▼
Phase 6
Russia-Compatible API Research
   │
   ▼
Phase 7
Google Flights Price Insights /
Market Intelligence Research
   │
   ▼
Phase 11
Cloud-Based Telegram Alerts
```

---

# Phase 3.2 — Historical Search Prioritization

## Priority

🥇 Highest priority.

## Status

⏳ Next implementation phase.

## Goal

Use historical fare data to determine which search combinations should receive API budget priority.

The goal is:

> Reduce unnecessary exploration API cost while preserving the ability to discover new cheap routes and dates.

---

## Current Problem

The existing adaptive search system learns from the current search run.

Phase 3.2 adds another source of intelligence:

```text
Current search results
        +
Historical search results
        ↓
Better search priority
```

---

## Proposed Flow

```text
New search request
        ↓
Generate candidate airport/date combinations
        ↓
Check historical database
        ↓
Calculate priority
        ↓
Prioritize historically promising combinations
        ↓
Reserve some budget for exploration
        ↓
Run API searches
        ↓
Evaluate results
        ↓
Save new results
        ↓
Improve future prioritization
```

---

## Important Design Principle

Historical data must influence priority.

Historical data must NOT completely control the search.

The algorithm should avoid:

```text
SVO was cheap historically
        ↓
Always search SVO
        ↓
Never search VKO
```

Instead:

```text
SVO
→ High priority

VKO
→ Exploration priority

DME
→ Lower priority
```

The system should continue discovering new opportunities.

---

## Suggested Priority Inputs

Potential inputs:

* Historical average price.
* Historical minimum price.
* Number of observations.
* Recency of observations.
* Route/airport pair.
* Exact travel-date history.
* Trip duration similarity.
* Historical success rate.
* Number of searches with no priced result.

The first implementation should remain simple.

Do not build an overly complex ML model.

---

## API Budget Goal

Phase 3.2 should not increase the API budget.

It should improve how the existing budget is allocated.

Example:

```text
API budget = 8

Without historical prioritization:
8 searches distributed broadly.

With historical prioritization:
5 searches → high-confidence promising areas
2 searches → medium-confidence areas
1 search → exploration
```

The exact allocation should be determined from the existing architecture and tested carefully.

---

# Phase 6 — Russia-Compatible Flight API Research

## Priority

🥈 Second priority.

## Status

⏳ Research later.

## Goal

Find legitimate alternative flight-data providers that add meaningful coverage for Russia.

The current primary provider is SerpApi.

Another provider should only be added if it genuinely improves coverage or verification.

---

## Target Coverage

Research:

* India → Moscow.
* International → Russia.
* Moscow → Murmansk.
* Moscow → Russian domestic destinations.
* Russian airlines.
* Russian airport coverage.

---

## Evaluation Criteria

For each provider:

| Criteria                        | Importance |
| ------------------------------- | ---------- |
| Russia domestic coverage        | ⭐⭐⭐⭐⭐      |
| International → Russia coverage | ⭐⭐⭐⭐⭐      |
| Real-time fares                 | ⭐⭐⭐⭐⭐      |
| Price accuracy                  | ⭐⭐⭐⭐⭐      |
| Airline coverage                | ⭐⭐⭐⭐⭐      |
| API cost                        | ⭐⭐⭐⭐       |
| Rate limits                     | ⭐⭐⭐⭐       |
| Booking/OTA information         | ⭐⭐⭐        |
| Free credits                    | ⭐⭐⭐        |
| Python integration              | ⭐⭐⭐        |

---

## Important Rule

Research first.

Do not spend large amounts of API credit testing providers without evidence that they support the required routes.

The provider must offer enough incremental value to justify:

* Additional integration complexity.
* Additional API costs.
* Additional maintenance.

---

# Phase 7 — Google Flights Price Insights / Market Intelligence

## Priority

🥉 Later intelligence phase.

## Status

⏳ Research required.

## Goal

Investigate whether legitimate access exists to broader Google Flights price-insight or market-intelligence data.

This replaces the earlier concept of building an AI/ML price-prediction system.

---

## Desired Concept

Combine:

```text
Our historical database
        +
Current SerpApi search
        +
Broader market-level price intelligence
```

Potential result:

```text
Current fare: ₹63,510

Our historical average: ₹64,555
Our historical low: ₹60,939

Market insight: Low

Recommendation:
Good fare, but not a historical low.
```

---

## Important Caveat

Do not assume a public Google Flights Price Insights API exists.

Before implementation:

1. Research Google's official API offerings.
2. Determine whether the required price-insight information is legitimately accessible.
3. Determine whether SerpApi or another legitimate provider exposes equivalent information.
4. Review terms and technical limitations.

Do not:

* Scrape Google Flights.
* Reverse-engineer undocumented endpoints.
* Build the project around fragile unofficial APIs.

---

## Desired Outcome

The feature should improve the agent's ability to answer:

> "Is this fare genuinely cheap, or should I wait?"

---

# Phase 11 — Cloud-Based Telegram Alerts

## Priority

Later.

## Status

⏳ Deferred.

## Goal

Allow fare alerts to work when the user's PC is turned off.

---

## Desired Architecture

```text
Cloud Scheduler
        ↓
Flight Fare Agent
        ↓
Limited API Search
        ↓
Historical Comparison
        ↓
Fare Evaluation
        ↓
Threshold / Event Detection
        ↓
Telegram Alert
```

---

## Example Alert

```text
🚨 FLIGHT FARE ALERT

HYD → SVO
2027-01-20 → 2027-01-25

Current fare: ₹60,500
Historical low: ₹60,939

🔥 NEW HISTORICAL LOW

Recommendation:
Strong booking opportunity.
```

---

## Timing

Do not implement now.

The user's trip is approximately seven months away and API credits are limited.

Cloud monitoring should be introduced when:

* Travel date approaches.
* API strategy is finalized.
* Sufficient API credits are available.
* Phase 3.2 has reduced unnecessary searches.

---

# Dropped / Deferred Phases

## Phase 10 — Booking / OTA Intelligence

### Status

❌ Dropped for now.

### Reason

The primary objective is finding the cheapest dates and fares.

Booking-token resolution may return limited booking options and may not identify the user's preferred OTA.

The user can manually search/book after finding the best fare.

This feature is not worth prioritizing over search intelligence.

---

## Continuous High-Frequency Monitoring

### Status

❌ Not planned now.

The user does not want to waste API credits monitoring prices daily when travel is still months away.

---

## Broad AI Fare Prediction

### Status

❌ Replaced.

The previous concept of building an AI/ML fare prediction engine is replaced by researching Google Flights Price Insights / broader market intelligence.

---

## Full Productization

### Status

❌ Not needed.

This is a personal project.

Do not build:

* Multi-user authentication.
* SaaS infrastructure.
* Commercial UI.
* Billing.
* Product analytics.

---

# Future Release Strategy

Potential version progression:

```text
v2.0.0
Current stable baseline

v2.1.0
Phase 3.2 Historical Search Prioritization

v2.2.0
Potential Russia-compatible provider integration

v2.3.0
Potential market intelligence integration

v3.0.0
Cloud-based monitoring and alerts
```

Version numbers are suggestions only.

Use semantic versioning based on actual change scope.

---

# Final Product Vision

The long-term personal fare agent should work like this:

```text
User defines:
Route
Travel window
Trip duration
API budget
        ↓
Agent checks historical knowledge
        ↓
Agent prioritizes promising searches
        ↓
Agent reserves budget for exploration
        ↓
Live fare search
        ↓
Historical fare comparison
        ↓
Market intelligence
        ↓
Best-date recommendation
        ↓
"Book now" / "Wait" guidance
        ↓
Optional cloud monitoring
        ↓
Telegram alert
```

The core optimization target remains:

> Find the cheapest travel dates with the smallest reasonable API cost.
