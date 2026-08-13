import json
from hashlib import sha256

from openai import AsyncOpenAI, OpenAIError

from src.agents.understanding.base import UnderstandingProviderError
from src.agents.understanding.models import UnderstandingContext, UnderstandingResult

_INSTRUCTIONS = """You extract structured meaning from a Vietnamese ride-hailing
voice transcript. Use the active workflow and current step as context. Extract only
facts expressed by the user. Never infer an address, booking ID, confirmation,
vehicle type, or correction that was not stated.

For RIDE_BOOKING, the ONLY collectable user fields are pickup_query,
destination_query, and vehicle_type. Never extract or request private personal data
(phone number, email, full name, ID, payment info). Leave phone_number null for
booking turns.

If any of the three booking fields is missing, return null so the agent can ask
again. Supported vehicle_type values: 4_SEAT, 7_SEAT, PREMIUM.

HUMAN_HANDOFF includes requests for a person, complaints, or emergencies. Return
UNKNOWN when the intent is not supported. This is language understanding only: never
execute tools or decide business transitions."""


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
