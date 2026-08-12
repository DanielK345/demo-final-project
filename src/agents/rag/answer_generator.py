from typing import Protocol

from src.agents.tools.schemas import KnowledgeDocument


class GroundedAnswerGenerator(Protocol):
    async def generate(
        self,
        *,
        question: str,
        documents: list[KnowledgeDocument],
    ) -> str: ...


class ExtractiveAnswerGenerator:
    """Deterministic MVP generator that can only return retrieved content."""

    def __init__(self, max_documents: int = 2, max_characters: int = 500) -> None:
        if max_documents < 1 or max_characters < 1:
            raise ValueError("answer limits must be positive")
        self.max_documents = max_documents
        self.max_characters = max_characters

    async def generate(
        self,
        *,
        question: str,
        documents: list[KnowledgeDocument],
    ) -> str:
        del question  # The deterministic implementation does not infer new facts.
        contents = [
            " ".join(document.content.split())
            for document in documents[: self.max_documents]
            if document.content.strip()
        ]
        answer = " ".join(contents)
        if len(answer) <= self.max_characters:
            return answer
        return f"{answer[: self.max_characters - 3].rstrip()}..."
