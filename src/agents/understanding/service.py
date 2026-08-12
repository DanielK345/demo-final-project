from src.agents.understanding.base import (
    LanguageUnderstandingPort,
    UnderstandingProviderError,
)
from src.agents.understanding.models import UnderstandingContext, UnderstandingResult


class ResilientUnderstandingService:
    def __init__(
        self,
        primary: LanguageUnderstandingPort,
        fallback: LanguageUnderstandingPort,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    async def understand(
        self,
        transcript: str,
        context: UnderstandingContext,
    ) -> UnderstandingResult:
        try:
            return await self.primary.understand(transcript, context)
        except UnderstandingProviderError:
            return await self.fallback.understand(transcript, context)
