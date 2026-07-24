import os
from dotenv import load_dotenv
import serpapi


# ============================================
# 1. Load API credentials
# ============================================

load_dotenv()

api_key = os.getenv("SERPAPI_API_KEY")

if not api_key:
    raise ValueError(
        "SERPAPI_API_KEY not found. "
        "Please check your .env file."
    )


# ============================================
# 2. Create SerpApi client
# ============================================

client = serpapi.Client(api_key=api_key)


# ============================================
# 3. Search Google Flights
# ============================================

params = {
    "engine": "google_flights",
    "departure_id": "HYD",
    "arrival_id": "HEL",
    "outbound_date": "2027-01-25",
    "return_date": "2027-01-31",
    "currency": "INR",
    "hl": "en",
    "type": "1",
}

results = client.search(params)


# ============================================
# 4. Get flight results
# ============================================

best_flights = results.get("best_flights", [])
other_flights = results.get("other_flights", [])

all_flights = best_flights + other_flights


# ============================================
# 5. Display results
# ============================================

print()
print("=" * 70)
print("FLIGHT SEARCH RESULTS")
print("=" * 70)

print(f"Route: HYD → HEL")
print(f"Departure: 25-Jan-2027")
print(f"Return: 31-Jan-2027")
print(f"Flights found: {len(all_flights)}")

print("=" * 70)


for index, flight in enumerate(all_flights, start=1):

    price = flight.get("price", "N/A")
    duration = flight.get("total_duration", "N/A")

    print()
    print(f"OPTION {index}")
    print("-" * 70)
    print(f"Price: ₹{price}")
    print(f"Total duration: {duration}")

    segments = flight.get("flights", [])

    for segment in segments:

        airline = segment.get("airline", "Unknown")

        departure = segment.get(
            "departure_airport",
            {}
        )

        arrival = segment.get(
            "arrival_airport",
            {}
        )

        print(
            f"  {airline}: "
            f"{departure.get('id')} → "
            f"{arrival.get('id')}"
        )

print()
print("=" * 70)