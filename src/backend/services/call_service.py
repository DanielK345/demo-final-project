import hashlib

from src.backend.repositories.persistence_repository import PersistenceRepository


class CallService:
    def __init__(self, repository: PersistenceRepository | None = None) -> None:
        self._repository = repository or PersistenceRepository()

    async def create_call(self, customer_phone: str) -> dict[str, str]:
        guest = await self._repository.ensure_voice_guest(customer_phone)
        session = await self._repository.create_session(
            user_id=str(guest["user_id"]), channel="TELEPHONY", device_id="phone", phone=customer_phone,
        )
        call = await self._repository.create_call(
            session_id=str(session["session_id"]),
            customer_phone_hash=hashlib.sha256(customer_phone.encode()).hexdigest(),
        )
        return {"call_id": str(call["call_id"]), "session_id": str(session["session_id"]), "status": str(call["status"])}
