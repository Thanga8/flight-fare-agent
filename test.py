from flight_search.google_flights_url import (
    build_google_flights_url,
)


url = build_google_flights_url(
    origin="HYD",
    destination="SVO",
    departure_date="2027-01-20",
    return_date="2027-01-25",
)

print()
print("=" * 70)
print("GOOGLE FLIGHTS URL TEST")
print("=" * 70)
print(url)
print("=" * 70)