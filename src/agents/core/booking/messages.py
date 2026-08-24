from src.agents.core.booking.state import BookingData
from src.agents.core.booking_types import VehicleType


def passenger_confirmation(data: BookingData) -> str:
    if data.passenger_count is None:
        return ""
    return f", cho {data.passenger_count} hành khách"


def vehicle_label(data: BookingData) -> str:
    if data.vehicle_display_name:
        return data.vehicle_display_name
    try:
        return VehicleType(data.vehicle_type).spoken_label
    except ValueError:
        return data.vehicle_type or "loại xe đã chọn"


def format_fare(data: BookingData) -> str:
    amount = data.estimated_fare_amount
    currency = data.estimated_currency or "VND"
    if amount is None:
        return "chưa xác định"
    if currency == "VND":
        return f"{amount:,.0f} đồng".replace(",", ".")
    return f"{amount:,.0f} {currency}"
