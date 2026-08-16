from typing import Any


def tool_definition(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


SERVICE_TOOLS = [
    tool_definition(
        "respond",
        "Nói một câu ngắn tự nhiên với khách; đặt expects_response=true nếu đang hỏi khách.",
        {
            "message": {"type": "string"},
            "expects_response": {"type": "boolean"},
        },
        ["message", "expects_response"],
    ),
    tool_definition(
        "update_booking",
        "Lưu chi tiết đặt xe khách nói rõ. Chỉ lưu pickup_query/destination_query khi có tên nơi hoặc địa chỉ cụ thể; nếu khách chỉ nói loại nơi như bệnh viện thì hãy hỏi rõ bằng respond.",
        {
            "pickup_query": {"type": "string"},
            "destination_query": {"type": "string"},
            "vehicle_type": {"type": "string", "enum": ["MOTORBIKE", "CAR_4", "CAR_7"]},
            "passenger_count": {"type": "integer", "minimum": 1, "maximum": 50},
            "luggage_count": {"type": "integer", "minimum": 0, "maximum": 50},
            "vehicle_preference": {"type": "string"},
            "phone_number": {"type": "string"},
        },
    ),
    tool_definition("search_pickup", "Yêu cầu backend phân giải pickup_query trong state.", {}),
    tool_definition("search_destination", "Yêu cầu backend phân giải destination_query trong state.", {}),
    tool_definition(
        "select_place",
        "Chọn một địa điểm từ candidates backend đã trả.",
        {
            "target": {"type": "string", "enum": ["pickup", "destination"]},
            "index": {"type": "integer", "minimum": 1},
        },
        ["target", "index"],
    ),
    tool_definition("request_vehicle_options", "Yêu cầu backend trả các xe phù hợp với state.", {}),
    tool_definition(
        "select_vehicle",
        "Chọn xe từ vehicle_options backend đã trả; dùng option_id chính xác trong state.",
        {"option_id": {"type": "string"}},
        ["option_id"],
    ),
    tool_definition(
        "estimate_fare",
        "Yêu cầu backend báo giá ngay khi đã có hai địa điểm và loại xe; số hành khách/hành lý không bắt buộc.",
        {},
    ),
    tool_definition(
        "request_booking_confirmation",
        "Tạo câu tóm tắt deterministic và chuyển state sang chờ khách xác nhận.",
        {},
    ),
    tool_definition("confirm_booking", "Tạo booking sau lời xác nhận rõ ràng của khách.", {}),
    tool_definition(
        "request_cancellation_confirmation",
        "Hỏi xác nhận trước khi hủy một booking đã tạo.",
        {},
    ),
    tool_definition("confirm_cancellation", "Hủy booking sau khi khách vừa xác nhận rõ ràng.", {}),
    tool_definition(
        "request_abandon_confirmation",
        "Yêu cầu xác nhận khi khách có vẻ muốn dừng một booking draft; không xóa state.",
        {},
    ),
    tool_definition(
        "confirm_abandon_booking",
        "Xóa booking draft chỉ sau khi khách vừa xác nhận rõ ràng muốn dừng.",
        {},
    ),
    tool_definition(
        "keep_booking",
        "Giữ và tiếp tục booking draft khi khách phủ nhận ý định dừng hoặc đính chính.",
        {},
    ),
    tool_definition(
        "start_rebook",
        "Bắt đầu draft đặt xe mới từ chuyến đã hủy/hoàn tất trước đó; không tạo booking và không dùng lại giá cũ.",
        {},
    ),
    tool_definition(
        "lookup_trip",
        "Yêu cầu backend tra cứu chuyến bằng mã chuyến hoặc số điện thoại khách vừa cung cấp.",
        {"booking_id": {"type": "string"}, "phone_number": {"type": "string"}},
    ),
    tool_definition(
        "select_trip",
        "Chọn một chuyến từ danh sách kết quả tra cứu; dùng vị trí hiển thị bắt đầu từ 1.",
        {"index": {"type": "integer", "minimum": 1}},
        ["index"],
    ),
    tool_definition(
        "retrieve_knowledge",
        "Tra cứu nguồn dữ liệu dịch vụ trước khi trả lời câu hỏi về chính sách, giá hoặc ưu đãi.",
        {"query": {"type": "string"}},
        ["query"],
    ),
    tool_definition(
        "handoff",
        "Chuyển người thật khi khách yêu cầu, có tình huống khẩn cấp hoặc không thể xử lý an toàn.",
        {"reason": {"type": "string"}},
        ["reason"],
    ),
]


TOOL_DEFINITIONS = {item["function"]["name"]: item for item in SERVICE_TOOLS}


def definition(name: str) -> dict[str, Any]:
    return TOOL_DEFINITIONS[name]
