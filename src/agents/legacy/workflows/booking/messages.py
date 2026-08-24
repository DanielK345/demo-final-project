"""Formatting used only by the retired deterministic booking workflow."""

from src.agents.core.booking_types import RecommendationReason
from src.agents.tools.schemas import VehicleOption


def format_option_fare(option: VehicleOption) -> str:
    if option.currency == "VND":
        return f"{option.fare_amount:,.0f} đồng".replace(",", ".")
    return f"{option.fare_amount:,.0f} {option.currency}"


def recommendation_reason_text(reason: RecommendationReason | None) -> str:
    return {
        RecommendationReason.PASSENGER_FIT: " vì phù hợp số hành khách",
        RecommendationReason.LUGGAGE_FIT: " vì phù hợp lượng hành lý",
        RecommendationReason.COMFORT: " theo ưu tiên thoải mái của bạn",
        RecommendationReason.ECONOMY: " theo ưu tiên tiết kiệm của bạn",
        RecommendationReason.PREMIUM: " theo ưu tiên cao cấp của bạn",
        None: "",
    }[reason]
