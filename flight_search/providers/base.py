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
    
    @abstractmethod
    def search_open_jaw(
        self,
        outbound_departure_id: str,
        outbound_arrival_id: str,
        return_departure_id: str,
        return_arrival_id: str,
        outbound_date: str,
        return_date: str,
    ) -> Dict[str, Any]:
        raise NotImplementedError