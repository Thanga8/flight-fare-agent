from flight_search.providers.serpapi_provider import SerpApiProvider


# ==========================================
# CONFIGURATION
# ==========================================

OUTBOUND_DEPARTURE = "HYD"
OUTBOUND_ARRIVAL = "SVO"

RETURN_DEPARTURE = "HEL"
RETURN_ARRIVAL = "HYD"

OUTBOUND_DATE = "2027-01-20"
RETURN_DATE = "2027-01-25"


# ==========================================
# INITIALIZE PROVIDER
# ==========================================

provider = SerpApiProvider()


# ==========================================
# RUN OPEN JAW SEARCH
# ==========================================

print()
print("=" * 70)
print("OPEN JAW PROVIDER TEST")
print("=" * 70)

print(
    f"Outbound: "
    f"{OUTBOUND_DEPARTURE} → "
    f"{OUTBOUND_ARRIVAL}"
)

print(
    f"Return: "
    f"{RETURN_DEPARTURE} → "
    f"{RETURN_ARRIVAL}"
)

print(
    f"Dates: "
    f"{OUTBOUND_DATE} → "
    f"{RETURN_DATE}"
)

print("=" * 70)

try:

    response = provider.search_open_jaw(
        outbound_departure_id=OUTBOUND_DEPARTURE,
        outbound_arrival_id=OUTBOUND_ARRIVAL,
        return_departure_id=RETURN_DEPARTURE,
        return_arrival_id=RETURN_ARRIVAL,
        outbound_date=OUTBOUND_DATE,
        return_date=RETURN_DATE,
    )

    print()
    print("API RESPONSE RECEIVED")
    print("-" * 70)

    print("Response type:")
    print(type(response))

    print()
    print("Available attributes:")

    print(
        dir(response)
    )

    print()
    print("Raw response object:")

    print(
        response
    )

except Exception as error:

    print()
    print("OPEN JAW API ERROR")
    print("-" * 70)

    print(error)