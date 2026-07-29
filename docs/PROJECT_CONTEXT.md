# Flight Fare Agent — Project Context

## 1. Project Overview

The Flight Fare Agent is a personal Python-based flight fare intelligence system.

Its primary purpose is to search flexible travel-date combinations and identify the cheapest and most attractive flight options while using a limited flight-search API budget efficiently.

The project started as a simple flight-search script and has evolved into a system with:

* Flexible-date search.
* Adaptive API search.
* Flight scoring.
* SQLite historical storage.
* Historical fare evaluation.
* Fare ratings.
* Search-to-search price comparison.
* Telegram reporting.
* Historical search commands.

The project is currently at stable version:

`v2.0.0`

---

## 2. Primary Objective

The user's primary goal is:

> Find the cheapest travel dates and flight combinations.

The user is not primarily trying to:

* Find the exact booking provider.
* Automatically book flights.
* Build a commercial travel product.
* Run high-frequency fare monitoring.
* Build a machine-learning price prediction system.

The agent should therefore prioritize:

1. Date discovery.
2. Fare discovery.
3. Efficient API usage.
4. Historical fare intelligence.
5. Clear recommendations.

---

## 3. Current Use Case

The current main travel search is approximately:

```text
Origin:
HYD

Destination:
MOW

Travel window:
2027-01-20 → 2027-02-13

Trip duration:
5–6 days
```

The destination may represent a broader Moscow search involving multiple Moscow airports such as:

* SVO
* DME
* VKO

The system can evaluate airport combinations and rank them.

The project should remain configurable for future routes.

---

## 4. Current Stable Architecture

The high-level architecture is:

```text
User
  │
  ▼
Telegram Bot
  │
  ▼
Search Orchestration
  │
  ├───────────────┐
  ▼               ▼
Search Planner    SQLite Historical Data
  │               │
  ▼               │
SerpApi           │
  │               │
  ▼               │
Raw Flight Data   │
  │               │
  ▼               │
Result Extraction │
  │               │
  └───────┬───────┘
          ▼
    Flight Results
          │
          ▼
       Scoring
          │
          ▼
   Fare Evaluation
          │
          ▼
 Recommendations
          │
          ▼
 Telegram Report
```

The existing implementation already has a working search pipeline and should not be unnecessarily rewritten.

---

## 5. Search Process

The current search architecture uses a flexible-date approach.

Conceptually:

```text
Search window
    ↓
Generate valid departure/return combinations
    ↓
Generate airport combinations
    ↓
Create initial exploration plan
    ↓
Execute exploration
    ↓
Evaluate airport performance
    ↓
Create adaptive search plan
    ↓
Execute adaptive searches
    ↓
Collect priced results
    ↓
Rank and score results
```

The adaptive search system is one of the project's most important components.

The current search process already uses a split between:

* Phase 1: Exploration.
* Phase 2: Adaptive search.

The purpose is to learn enough from initial searches to direct remaining API budget toward promising combinations.

---

## 6. API

The primary search provider is SerpApi using Google Flights data.

The API is treated as a limited resource.

The user has already consumed a significant amount of available API credits.

Therefore:

```text
API credits = valuable
```

The system should avoid unnecessary live calls.

The user's travel date is approximately seven months away, so continuous monitoring is not currently appropriate.

The user may obtain additional credits later, but the immediate goal is to make the existing API budget more efficient.

---

## 7. Existing Search Result Data

The normalized flight result includes information such as:

* Departure airport.
* Arrival airport.
* Departure date.
* Return date.
* Price.
* Duration.
* Trip days.
* Raw flight information.
* Database ID.

The underlying SerpApi flight object can contain richer data, including:

* Flight segments.
* Layovers.
* Airline.
* Flight number.
* Aircraft.
* Travel class.
* Duration.
* Carbon emissions.
* Departure token.

The project intentionally does not currently make booking/OTA resolution a core feature.

---

## 8. SQLite Historical Database

SQLite is the project's local historical data store.

The search pipeline saves priced search results.

Historical data is used for:

* Cheapest recorded fare.
* Historical average.
* Historical low.
* Fare evaluation.
* Fare rating.
* Historical confidence.
* Search-to-search price comparison.

The database allows the agent to evolve from:

> "This is the cheapest result I found today."

to:

> "This fare is cheap compared with fares previously observed."

The historical system is already integrated into the project.

---

## 9. Fare Evaluation

The system evaluates flight fares using historical data.

Current concepts include:

* Fare rating.
* Fare score.
* Assessment.
* Historical average.
* Historical low.
* Comparison level.
* Confidence.

Examples of fare assessments include:

```text
NEW_HISTORICAL_LOW
GOOD_PRICE
ABOVE_AVERAGE
```

The exact fare evaluation logic should remain in the evaluation layer.

Telegram should display the evaluation rather than recreate it.

---

## 10. Scoring

The scoring engine evaluates flight options based on multiple dimensions.

Current components include:

```text
Price score
Duration score
Stops score
Convenience score
        ↓
Final score
```

The system can produce a final score such as:

```text
Final score: 89.75 / 100
```

The scoring system and fare evaluation system are related but distinct.

Scoring answers:

> "Which flight is the best overall option among current search results?"

Fare evaluation answers:

> "How good is this fare compared with historical observations?"

Both should remain available.

---

## 11. Recommendations

Current recommendation concepts include:

* Best Overall.
* Cheapest.
* Fastest.
* Best 5-Day Trip.
* Best 6-Day Trip.
* Distinct Alternative.

The project has already addressed duplicate recommendations so that the output is more useful.

The recommendation layer should continue using the existing scoring and evaluation systems rather than implementing a second independent ranking system.

---

## 12. Previous Search Price Comparison

The project also compares the current cheapest fare against the previous search.

This answers:

> "Did the price change since I last searched?"

Example:

```text
Current cheapest: ₹63,510
Previous cheapest: ₹63,510
Price difference: ₹0
Percentage change: 0%
Price direction: UNCHANGED
Previous search: 2026-07-28 13:03:15
```

This is separate from historical fare evaluation.

There are two independent intelligence dimensions:

### Historical intelligence

> Is the current fare good compared with historical observations?

### Search-to-search intelligence

> Did the cheapest fare change since my previous search?

Both should be retained.

---

## 13. Telegram Bot

Telegram is the current user interface.

Current commands:

```text
/start
/help
/search
/latest
/best
/history
```

### `/search`

Runs a fresh live flight search.

This consumes API credits.

It returns:

* Search summary.
* Best Overall.
* Fare rating.
* Historical assessment.
* Confidence.
* Recommendation.
* Other top options.
* Price movement.

### `/latest`

Shows the most recent search results from SQLite.

It does not perform a new live search.

### `/best`

Shows the cheapest fare historically recorded for the route associated with the latest search.

It includes when the fare was recorded.

It does not perform a new live search.

### `/history`

Shows recent historical fare observations.

It does not perform a new live search.

### `/help`

Shows available commands.

---

## 14. Current Telegram Output Concept

The current Telegram report is approximately:

```text
✈️ FLIGHT FARE UPDATE

📊 Search Summary
• API searches: 4
• Priced results: 4

🏆 BEST OVERALL

✈️ HYD → SVO
📅 2027-01-20 → 2027-01-25
💰 ₹63,510

★★★☆☆ Good Deal

📉 Below average historical pricing.
📊 Confidence: NONE

💡 Good fare. Worth considering.

💰 OTHER TOP OPTIONS

1. ₹66,149
✈️ HYD → SVO
📅 2027-01-20 → 2027-01-26
⭐ Score: 62.54

...

📊 PRICE MOVEMENT

🟡 Fare unchanged

Current cheapest: ₹63,510
Previous search: ₹63,510

Change: ₹0 (0.00%)

🕒 Previous search:
2026-07-28 14:54:24
```

Formatting consistency is important.

Do not allow different layers to independently assign contradictory fare ratings.

---

## 15. Current Stable Baseline

The project is considered stable at:

`v2.0.0`

This version represents the current working system containing:

* Flexible-date search.
* Adaptive search.
* Flight scoring.
* Historical fare database.
* Historical fare evaluation.
* Fare ratings.
* Fare recommendations.
* Previous-search price comparison.
* Telegram integration.
* `/search`.
* `/latest`.
* `/best`.
* `/history`.
* `/help`.

---

## 16. Open Jaw

Open Jaw was previously explored as an experimental search capability.

It should not currently be treated as the primary production search strategy.

If Open Jaw code remains in the repository, it should be isolated from the stable round-trip search architecture.

The core system should remain focused on the current working round-trip search flow.

---

## 17. Booking / OTA Resolution

The project investigated using:

```text
departure_token
booking_token
selected_flights_json
```

to resolve booking options.

The conclusion was that this is not currently valuable enough for the project's primary goal.

The user primarily wants:

> Find the cheapest dates and fares.

A booking result may provide only one or limited booking providers and may not be the preferred OTA.

Therefore booking/OTA resolution is currently dropped from the roadmap.

---

## 18. Current Development Philosophy

The project should become progressively more intelligent without requiring excessive API usage.

The desired long-term model is:

```text
Past searches
      ↓
Historical knowledge
      ↓
Better search prioritization
      ↓
Fewer wasted API calls
      ↓
More useful current results
      ↓
More historical knowledge
      ↓
Improved future searches
```

This feedback loop is more important than adding unnecessary features.

---

## 19. Immediate Next Feature

The immediate next feature is:

### Phase 3.2 — Historical Search Prioritization

The system should use existing historical data to prioritize search combinations.

For example:

```text
Historical observations

SVO:
Frequently cheap
→ High priority

VKO:
Insufficient data
→ Exploration priority

DME:
Historically expensive
→ Lower priority
```

The system must still retain exploration.

The goal is:

```text
Prioritize promising searches
+
Continue discovering new opportunities
```

Not:

```text
Only search historically cheap routes
```

---

## 20. Long-Term Vision

The eventual personal fare assistant should answer:

> "What are the cheapest dates for my trip, how good is today's fare, and should I spend an API search on this combination?"

The system should increasingly combine:

```text
Current market search
        +
Historical observations
        +
Search prioritization
        +
Potential external market intelligence
        +
Cloud-based alerts
```

while minimizing API cost.

The project should remain simple enough for one person to maintain.
