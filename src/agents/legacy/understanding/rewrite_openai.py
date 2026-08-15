import json
from hashlib import sha256

from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from src.agents.context import ConversationContext
from src.agents.understanding.rewrite_base import (
    InvalidRewriteOutputError,
    RewriteProviderError,
    RewriteTimeoutError,
)
from src.agents.understanding.rewrite_models import RewriteDecision, RewriteResult

_INSTRUCTIONS = """Rewrite a Vietnamese voice user's message only when sanitized
conversation evidence resolves its contextual references. Preserve original_text
exactly. Every resolved reference must quote a phrase from the original message,
use a value already present in the supplied context, and cite its source_turn_id.
Never invent or infer a place, address, phone number, booking ID, confirmation,
intent, workflow, tool call, action, or state update. If evidence is insufficient,
return the original text unchanged and add the ambiguity 'insufficient_context'."""


class OpenAIContextualRewriteAdapter:
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

    async def rewrite(
        self,
        original_text: str,
        context: ConversationContext,
        decision: RewriteDecision,
    ) -> RewriteResult:
        prompt_context = context.model_dump(
            mode="json",
            exclude={"session_id", "raw_transcript"},
        )
        prompt = json.dumps(
            {
                "original_text": original_text,
                "rewrite_reasons": [reason.value for reason in decision.reasons],
                "context": prompt_context,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            response = await self.client.responses.parse(
                model=self.model,
                instructions=_INSTRUCTIONS,
                input=prompt,
                text_format=RewriteResult,
                reasoning={"effort": self.reasoning_effort},
                max_output_tokens=700,
                store=False,
                safety_identifier=sha256(context.session_id.encode()).hexdigest(),
                timeout=self.timeout_seconds,
            )
        except (APITimeoutError, TimeoutError) as exc:
            raise RewriteTimeoutError("OpenAI rewrite timed out") from exc
        except OpenAIError as exc:
            raise RewriteProviderError("OpenAI rewrite failed") from exc
        except ValueError as exc:
            raise InvalidRewriteOutputError("OpenAI rewrite output was invalid") from exc

        parsed = response.output_parsed
        if parsed is None:
            raise InvalidRewriteOutputError("OpenAI returned no parseable rewrite result")
        return parsed
