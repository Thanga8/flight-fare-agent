import os

from dotenv import load_dotenv

from flight_search.providers.flightapi_provider import (
    FlightApiProvider
)


load_dotenv()


provider = FlightApiProvider(
    api_key=os.getenv(
        "FLIGHTAPI_API_KEY"
    )
)


print("=" * 70)
print("FLIGHTAPI RAW RESPONSE TEST")
print("=" * 70)


payload = provider.search_round_trip(

    departure_id="HYD",

    arrival_id="SVO",

    outbound_date="2027-02-08",

    return_date="2027-02-13",
)


print()
print("RESPONSE TYPE:")
print(type(payload))


print()
print("TOP-LEVEL KEYS:")

if isinstance(payload, dict):

    print(
        payload.keys()
    )

else:

    print(
        "Response is not a dictionary."
    )


print()
print("RAW RESPONSE:")
print("=" * 70)

print(payload)

print("=" * 70)