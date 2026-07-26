from search_history import (
    analyze_price_intelligence,
)


print("=" * 70)
print("PRICE INTELLIGENCE TEST")
print("=" * 70)


# ==========================================
# TEST 1 — EXACT DATE HISTORY
# ==========================================

print()
print("TEST 1 — EXACT DATE HISTORY")
print("-" * 70)

result = analyze_price_intelligence(

    origin="HYD",

    destination="SVO",

    departure_date="2027-02-08",

    return_date="2027-02-13",

    current_price=65000,

)

print(result)


# ==========================================
# TEST 2 — NO EXACT DATE
# SHOULD FALL BACK TO COMPARABLE HISTORY
# ==========================================

print()
print("TEST 2 — COMPARABLE HISTORICAL DATA")
print("-" * 70)

result = analyze_price_intelligence(

    origin="HYD",

    destination="SVO",

    departure_date="2027-01-21",

    return_date="2027-01-26",

    current_price=70000,

)

print(result)


# ==========================================
# TEST 3 — COMPLETELY NEW ROUTE
# ==========================================

print()
print("TEST 3 — NO HISTORICAL DATA")
print("-" * 70)

result = analyze_price_intelligence(

    origin="HYD",

    destination="JFK",

    departure_date="2027-03-01",

    return_date="2027-03-06",

    current_price=80000,

)

print(result)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)