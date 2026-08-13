import re

_AMBIGUOUS_LOCATION_PATTERNS = (
    re.compile(r"^(?:về\s+|đến\s+|tới\s+)?nhà(?:\s+(?:tôi|mình|em|anh|chị|bác))?$", re.IGNORECASE),
    re.compile(r"^(?:ở|đến|tới|về)?\s*(?:đó|đấy|kia)$", re.IGNORECASE),
    re.compile(r"^(?:chỗ|địa điểm)\s+(?:cũ|lúc nãy|hôm trước)$", re.IGNORECASE),
)


def is_ambiguous_location_text(value: str | None) -> bool:
    """Return true when a location reference has no resolvable address evidence."""
    if value is None:
        return True
    normalized = " ".join(value.strip(" .!?").split())
    if not normalized:
        return True
    return any(pattern.fullmatch(normalized) for pattern in _AMBIGUOUS_LOCATION_PATTERNS)
