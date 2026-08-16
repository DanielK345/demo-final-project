"""Live, non-mocked quality gate for the OpenAI transcript rewriter.

Run explicitly with a real OPENROUTER_API_KEY (or a direct OpenAI configuration):
    .venv/Scripts/python.exe scripts/live_voice_rewrite_check.py
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.services.transcript_rewriter import build_transcript_rewriter  # noqa: E402


@dataclass(frozen=True)
class LiveCase:
    text: str
    required_terms: tuple[str, ...]
    step: str
    expect_applied: bool | None = True


CASES = (
    LiveCase(
        "toi muon dat xe tu san bay tan son nhat den vin com dong khoi",
        ("Tôi", "Sân bay Tân Sơn Nhất", "Vincom Đồng Khởi"),
        "COLLECT_PICKUP",
    ),
    LiveCase(
        "don toi o lam mac tam mot den cho ben thanh",
        ("Landmark 81", "Chợ Bến Thành"),
        "COLLECT_PICKUP",
    ),
    LiveCase(
        "toi khong muon huy chuyen xe",
        ("không", "hủy"),
        "CANCEL_CONFIRM",
    ),
    LiveCase(
        "goi toi so 0901234567 ma AB-123 luc 19:30",
        ("0901234567", "AB-123", "19:30"),
        "COLLECT_PICKUP",
        expect_applied=None,
    ),
    LiveCase("dung roi", ("dung roi",), "CONFIRM", expect_applied=False),
)


async def main() -> int:
    rewriter = build_transcript_rewriter()
    if rewriter is None:
        print("FAIL: transcript rewriter is disabled or its configured provider key is missing", file=sys.stderr)
        return 2

    failures: list[str] = []
    for index, case in enumerate(CASES, start=1):
        result = await rewriter.rewrite(
            case.text,
            session_context={"current_workflow": "RIDE_BOOKING", "current_step": case.step},
            session_id=f"live-rewrite-{index}",
        )
        print(
            f"case={index} applied={result.applied} reason={result.reason} "
            f"confidence={result.confidence} duration_ms={result.duration_ms} "
            f"output={result.normalized_text!r}"
        )
        if result.reason == "provider_error":
            failures.append(f"case {index}: provider_error")
            break
        if case.expect_applied is not None and result.applied != case.expect_applied:
            failures.append(f"case {index}: applied={result.applied}, expected={case.expect_applied}")
        missing = [term for term in case.required_terms if term not in result.normalized_text]
        if missing:
            failures.append(f"case {index}: missing terms {missing}")

    if failures:
        print("LIVE QUALITY GATE FAILED", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("LIVE QUALITY GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
