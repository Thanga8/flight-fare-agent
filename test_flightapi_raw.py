import os

from dotenv import load_dotenv

from flight_search.providers.flightapi_provider import (
    FlightApiProvider
)


def main():
    """Run an explicitly requested, paid FlightAPI diagnostic."""
    if os.getenv("FLIGHTAPI_LIVE_PROBE", "").lower() != "true":
        raise SystemExit("Set FLIGHTAPI_LIVE_PROBE=true to authorize a paid provider request.")
    load_dotenv()
    provider = FlightApiProvider(api_key=os.getenv("FLIGHTAPI_API_KEY"))
    payload = provider.search_round_trip(
        departure_id="HYD", arrival_id="SVO",
        outbound_date="2027-02-08", return_date="2027-02-13",
    )
    print("FLIGHTAPI RAW RESPONSE")
    print(payload)


if __name__ == "__main__":
    main()
