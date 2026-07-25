from flight_search.providers.base import FlightSearchProvider
from flight_search.providers.serpapi_provider import SerpApiProvider


def get_default_provider() -> FlightSearchProvider:
    return SerpApiProvider()