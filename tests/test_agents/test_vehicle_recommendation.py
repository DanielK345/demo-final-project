from types import SimpleNamespace

import pytest

from src.agents.tools.schemas import VehicleOption
from src.agents.vehicle_recommendation import (
    OpenAIVehicleRecommender,
    RecommendationReason,
    VehicleRecommendation,
)


class FakeResponses:
    def __init__(self, recommendation: VehicleRecommendation) -> None:
        self.recommendation = recommendation

    async def parse(self, **kwargs):
        del kwargs
        return SimpleNamespace(output_parsed=self.recommendation)


class FakeClient:
    def __init__(self, recommendation: VehicleRecommendation) -> None:
        self.responses = FakeResponses(recommendation)


def option(option_id: str) -> VehicleOption:
    return VehicleOption(
        option_id=option_id,
        vehicle_type="BACKEND_DYNAMIC_TYPE",
        display_name="Backend dynamic vehicle",
        capacity=5,
        estimate_id=f"fare-{option_id}",
        fare_amount=123000,
        currency="VND",
    )


@pytest.mark.asyncio
async def test_recommender_accepts_only_backend_option_ids():
    invalid = OpenAIVehicleRecommender(
        api_key="test",
        model="test",
        timeout_seconds=1,
        reasoning_effort="none",
        client=FakeClient(
            VehicleRecommendation(
                option_id="invented-option",
                reason=RecommendationReason.COMFORT,
            )
        ),
    )

    result = await invalid.recommend(
        session_id="session-001",
        passenger_count=3,
        luggage_count=2,
        preference="comfortable",
        options=[option("trusted-option")],
    )

    assert result.option_id is None
    assert result.reason is None
