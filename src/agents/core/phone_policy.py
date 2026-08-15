import re

PHONE_CANDIDATE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)"
)
_VIETNAM_MOBILE_PATTERN = re.compile(r"^0(?:3|5|7|8|9)\d{8}$")


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return f"0{digits[2:]}" if digits.startswith("84") else digits


def extract_valid_mobile_phone(value: str) -> str | None:
    for match in PHONE_CANDIDATE_PATTERN.finditer(value):
        normalized = normalize_phone(match.group())
        if _VIETNAM_MOBILE_PATTERN.fullmatch(normalized):
            return normalized
    return None


def is_valid_mobile_phone(value: str) -> bool:
    return bool(_VIETNAM_MOBILE_PATTERN.fullmatch(normalize_phone(value)))
