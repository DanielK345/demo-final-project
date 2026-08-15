import json
from hashlib import sha256

from openai import AsyncOpenAI, OpenAIError

from src.agents.legacy.understanding.base import UnderstandingProviderError
from src.agents.legacy.understanding.models import UnderstandingContext, UnderstandingResult

_INSTRUCTIONS = """You are the single language-understanding boundary for a
Vietnamese ride-hailing voice agent. Use the active workflow, current phase, known
state, available candidates, and recent conversation to produce one structured turn.
Extract every explicitly stated booking slot. A short answer to a direct pickup or
destination question is that requested slot. Put changes such as 'thôi 4 chỗ đi' in
corrections as well as the corresponding typed slot. Set correction_requested when
the user wants to change information, even if no new value was supplied. Represent
candidate or vehicle choices with selection. Never invent an address, phone, booking
ID, confirmation, selection, price, or tool result. HUMAN_HANDOFF includes requests
for a person, complaints, or emergencies. Return UNKNOWN for unsupported content.
This component never chooses or executes external tools."""


class OpenAIUnderstandingAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 5.0,
        reasoning_effort: str = "none",
        base_url: str | None = None,
        max_retries: int = 0,
        client: AsyncOpenAI | None = None,
    ) -> None:
        if not api_key and client is None:
            raise ValueError("OpenAI API key is required")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.reasoning_effort = reasoning_effort
        self.client = client or AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
        )

    async def understand(
        self,
        transcript: str,
        context: UnderstandingContext,
    ) -> UnderstandingResult:
        context_text = json.dumps(
            {
                "transcript": transcript,
                "context": context.model_dump(
                    mode="json",
                    exclude={"session_id"},
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            response = await self.client.responses.parse(
                model=self.model,
                instructions=_INSTRUCTIONS,
                input=context_text,
                text_format=UnderstandingResult,
                reasoning={"effort": self.reasoning_effort},
                max_output_tokens=500,
                store=False,
                safety_identifier=sha256(context.session_id.encode()).hexdigest(),
                timeout=self.timeout_seconds,
            )
        except (OpenAIError, TimeoutError, ValueError) as exc:
            raise UnderstandingProviderError("OpenAI understanding failed") from exc

        parsed = response.output_parsed
        if parsed is None:
            raise UnderstandingProviderError(
                "OpenAI returned no parseable understanding result"
            )
        return parsed
