async def fetch_trip_status(session_id: str) -> dict[str, object]:
    return {"session_id": session_id, "status": "driver_arriving"}
