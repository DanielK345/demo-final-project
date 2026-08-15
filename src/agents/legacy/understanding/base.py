from typing import Protocol

from src.agents.legacy.understanding.models import UnderstandingContext, UnderstandingResult


class UnderstandingProviderError(RuntimeError):
    pass


class LanguageUnderstandingPort(Protocol):
    async def understand(
        self,
        transcript: str,
        context: UnderstandingContext,
    ) -> UnderstandingResult: ...
