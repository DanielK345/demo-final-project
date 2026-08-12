from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from src.agents.rag.knowledge_base import KnowledgeDocument


class RetrievalResult(BaseModel):
    document: KnowledgeDocument
    score: float = Field(ge=0, le=1)


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        """Return ranked, source-carrying documents for grounded answers."""

