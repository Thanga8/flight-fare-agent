from flight_search.search import search_flights


results = search_flights(
    departure_id="HYD",
    arrival_id="SVO",
    outbound_date="2027-01-22",
    return_date="2027-01-28",
)


print("\nBest flights:")
print(len(results.get("best_flights", [])))

print("\nOther flights:")
print(len(results.get("other_flights", [])))

print("\nError:")
print(results.get("error"))