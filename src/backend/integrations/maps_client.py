class MapsClient:
    async def geocode(self, query: str) -> dict[str, object]:
        return {"query": query, "lat": 0.0, "lng": 0.0}
