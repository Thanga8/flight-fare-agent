from abc import ABC, abstractmethod
from typing import Any, Dict


class FlightSearchProvider(ABC):
    name = "base"

    @abstractmethod
    def search_round_trip(
        self,
        departure_id: str,
        arrival_id: str,
        outbound_date: str,
        return_date: str,
    ) -> Dict[str, Any]:
        raise NotImplementedError