"""Small, dependency-free FAQ intent hints shared by text and LiveKit paths.

This module deliberately contains only normalized phrase matching.  It does
not load policy data or call a model, so it is safe to use on every turn.
Authoritative answers still come from the versioned policy catalog.
"""

from __future__ import annotations

import re
import unicodedata

_RULE_ALIASES: dict[str, tuple[str, ...]] = {
    "refund": (
        "hoan tien",
        "hoan lai",
        "tra lai tien",
        "yeu cau hoan",
        "bi tru tien",
    ),
    "price-change": (
        "tu y thay doi gia",
        "tu y thay doi",
        "thay doi gia",
        "gia sau xac nhan",
        "phat sinh phi",
    ),
    "price-confirmation": (
        "xac nhan gia",
        "gia du kien",
        "gia truoc khi dat",
        "phi truoc khi dat",
    ),
    "cancellation": (
        "phi huy",
        "chinh sach huy",
        "huy chuyen co mat phi",
        "huy chuyen va phi",
        "huy sau khi dat",
    ),
}

_GENERIC_FAQ_TERMS = (
    "chinh sach",
    "dieu khoan",
    "dich vu",
    "thanh toan",
    "hoa don",
    "hoat dong",
    "phu phi",
    "cach tinh phi",
)


def normalize_faq_text(text: str) -> str:
    """Normalize Vietnamese text for cheap, accent-insensitive phrase checks."""

    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_marks.replace("đ", "d").replace("Đ", "d").split())


def faq_rule_ids(text: str) -> tuple[str, ...]:
    normalized = normalize_faq_text(text)
    matches: list[tuple[int, str]] = []
    for rule_id, aliases in _RULE_ALIASES.items():
        longest = max((len(alias) for alias in aliases if re.search(rf"\b{re.escape(alias)}\b", normalized)), default=0)
        if longest:
            matches.append((longest, rule_id))
    matches.sort(key=lambda item: (-item[0], item[1]))
    return tuple(rule_id for _, rule_id in matches)


def faq_aliases(rule_id: str) -> tuple[str, ...]:
    return _RULE_ALIASES.get(rule_id, ())


def is_faq_query(text: str) -> bool:
    """Return whether a turn looks like a policy/FAQ question.

    Plain commands such as ``hủy chuyến này`` intentionally do not match.
    """

    normalized = normalize_faq_text(text)
    return bool(faq_rule_ids(text)) or any(
        re.search(rf"\b{re.escape(term)}\b", normalized) for term in _GENERIC_FAQ_TERMS
    )
