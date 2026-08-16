import json
from hashlib import sha256
from typing import Protocol

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel

from src.agents.core.booking_types import RecommendationReason
from src.agents.tools.schemas import VehicleOption
from src.config import Settings, get_settings


class VehicleRecommendation(BaseModel):
    option_id: str | None = None
    reason: RecommendationReason | None = None


class VehicleRecommendationPort(Protocol):
    async def recommend(
        self,
        *,
        session_id: str,
        passenger_count: int,
        luggage_count: int | None,
        preference: str | None,
        options: list[VehicleOption],
    ) -> VehicleRecommendation: ...


class NoRecommendation:
    async def recommend(self, **kwargs) -> VehicleRecommendation:
        del kwargs
        return VehicleRecommendation()


class OpenAIVehicleRecommender:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str,
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.reasoning_effort = reasoning_effort
        self.client = client or AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def recommend(self, **kwargs) -> VehicleRecommendation:
        session_id = str(kwargs.pop("session_id"))
        options = kwargs["options"]
        payload = {
            **kwargs,
            "options": [option.model_dump(mode="json") for option in options],
        }
        try:
            response = await self.client.responses.parse(
                model=self.model,
                instructions=(
                    "Recommend at most one ride option using only the supplied "
                    "available options and stated customer needs. Never invent an "
                    "option, price, capacity, or availability. Return no option when "
                    "the evidence is insufficient. Choose only one allowed reason code."
                ),
                input=json.dumps(payload, ensure_ascii=False),
                text_format=VehicleRecommendation,
                reasoning={"effort": self.reasoning_effort},
                max_output_tokens=250,
                store=False,
                safety_identifier=sha256(session_id.encode()).hexdigest(),
                timeout=self.timeout_seconds,
            )
        except (OpenAIError, TimeoutError, ValueError):
            return VehicleRecommendation()
        recommendation = response.output_parsed or VehicleRecommendation()
        valid_ids = {option.option_id for option in options if option.available}
        if recommendation.option_id not in valid_ids:
            return VehicleRecommendation()
        return recommendation


def build_vehicle_recommender(
    settings: Settings | None = None,
) -> VehicleRecommendationPort:
    config = settings or get_settings()
    api_key = config.llm_api_key_for(config.agent_llm_base_url)
    if not config.agent_llm_enabled or not api_key:
        return NoRecommendation()
    return OpenAIVehicleRecommender(
        api_key=api_key,
        model=config.agent_llm_model,
        timeout_seconds=config.agent_llm_timeout_seconds,
        reasoning_effort=config.agent_llm_reasoning_effort,
        base_url=config.agent_llm_base_url,
    )
