from search_history import (
    analyze_price_intelligence,
)


print("=" * 70)
print("UNIFIED PRICE INTELLIGENCE TEST")
print("=" * 70)


# ==========================================
# TEST 1 — KNOWN EXACT DATE
# ==========================================

print()
print("TEST 1 — KNOWN EXACT DATE")
print("-" * 70)

result = analyze_price_intelligence(

    origin="HYD",

    destination="MOW",

    departure_date="2027-02-08",

    return_date="2027-02-13",

    current_price=68000,

    min_trip_days=5,

    max_trip_days=6,

)

print(result)


# ==========================================
# TEST 2 — DIFFERENT PRICE
# ==========================================

print()
print("TEST 2 — EXPENSIVE CURRENT PRICE")
print("-" * 70)

result = analyze_price_intelligence(

    origin="HYD",

    destination="MOW",

    departure_date="2027-02-08",

    return_date="2027-02-13",

    current_price=100000,

    min_trip_days=5,

    max_trip_days=6,

)

print(result)


# ==========================================
# TEST 3 — NEW TRAVEL DATES
# ==========================================

print()
print("TEST 3 — NEW TRAVEL DATES")
print("-" * 70)

result = analyze_price_intelligence(

    origin="HYD",

    destination="MOW",

    departure_date="2027-02-01",

    return_date="2027-02-06",

    current_price=70000,

    min_trip_days=5,

    max_trip_days=6,

)

print(result)


# ==========================================
# TEST 4 — COMPLETELY NEW ROUTE
# ==========================================

print()
print("TEST 4 — NEW ROUTE")
print("-" * 70)

result = analyze_price_intelligence(

    origin="HYD",

    destination="LED",

    departure_date="2027-02-01",

    return_date="2027-02-06",

    current_price=70000,

    min_trip_days=5,

    max_trip_days=6,

)

print(result)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)