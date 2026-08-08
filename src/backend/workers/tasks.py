def process_geocoding(session_id: str) -> dict[str, str]:
    return {"session_id": session_id, "status": "queued"}


def generate_summary(call_id: str) -> dict[str, str]:
    return {"call_id": call_id, "status": "queued"}
