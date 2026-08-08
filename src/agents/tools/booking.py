async def create_booking(payload: dict[str, object]) -> dict[str, object]:
    return {"status": "pending", "payload": payload}
