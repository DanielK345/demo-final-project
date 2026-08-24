"""Place-search application boundary used by LiveKit function tools."""

from __future__ import annotations

from src.backend.services.place_search_service import PlaceSearchService
from src.voice_agent.session_data import PlaceCandidate


class PlaceToolsService:
    def __init__(self, search_service: PlaceSearchService | None = None) -> None:
        self._search_service = search_service or PlaceSearchService()

    def search(self, query: str, *, limit: int = 5) -> list[PlaceCandidate]:
        return [
            PlaceCandidate.model_validate(candidate)
            for candidate in self._search_service.search(query.strip(), limit=limit)
        ]
