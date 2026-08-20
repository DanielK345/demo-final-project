"""Conservative guard for short non-speech sounds misrecognized as words.

Energy VAD answers whether a frame is loud enough to resemble speech, but brief
noises such as a breath, cough, or microphone bump can still cross that threshold.
ASR systems may then turn the noise into a short filler.  This module combines
the ASR text with optional duration/confidence signals and deliberately blocks
only high-precision cases; meaningful short Vietnamese answers remain valid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[^\wÀ-ỹđĐ]+", flags=re.UNICODE)

# These are vocalisations/noise captions rather than actionable utterances.  Do
# not add ordinary short words here: "ừ", "dạ", "đúng", "không", "đi", and
# "xe" can all be legitimate turns in the booking flow.
_AMBIGUOUS_VOCALISATIONS = {
    "a",
    "ah",
    "à",
    "á",
    "ạ",
    "ơ",
    "ờ",
    "ớ",
    "ờm",
    "ừm",
    "hmm",
    "hm",
    "hừm",
    "hửm",
    "uh",
    "um",
    "oh",
    "khụ",
    "khụ khụ",
    "hắt xì",
    "hắt xì hơi",
}

_MEANINGFUL_BRIEF_UTTERANCES = {
    "alo",
    "có",
    "dạ",
    "đi",
    "đúng",
    "hủy",
    "không",
    "một",
    "hai",
    "ba",
    "thôi",
    "ừ",
    "vâng",
    "xe",
}


@dataclass(frozen=True)
class BriefSoundDecision:
    blocked: bool
    reason: str | None = None


def _canonicalize(text: str) -> str:
    return " ".join(part for part in _TOKEN_RE.sub(" ", text.casefold()).split() if part)


def detect_brief_ambiguous_sound(
    text: str,
    *,
    speech_duration_ms: float | None = None,
    confidence: float | None = None,
    max_duration_ms: int = 700,
    low_confidence_threshold: float = 0.40,
) -> BriefSoundDecision:
    """Return a blocking decision for a likely brief non-speech ASR result.

    ``speech_duration_ms=None`` is used by upload paths where the compressed
    container cannot be timed cheaply.  In that case only the explicit
    vocalisation list is blocked.  Duration/confidence heuristics are applied
    by the PCM16 WebSocket path where both signals are trustworthy.
    """

    canonical = _canonicalize(text)
    if not canonical:
        return BriefSoundDecision(blocked=True, reason="brief_ambiguous_sound")
    if canonical in _MEANINGFUL_BRIEF_UTTERANCES:
        return BriefSoundDecision(blocked=False)

    is_brief = speech_duration_ms is None or speech_duration_ms <= max_duration_ms
    if is_brief and canonical in _AMBIGUOUS_VOCALISATIONS:
        return BriefSoundDecision(blocked=True, reason="brief_ambiguous_sound")

    tokens = canonical.split()
    if (
        speech_duration_ms is not None
        and speech_duration_ms <= max_duration_ms
        and confidence is not None
        and confidence < low_confidence_threshold
        and len(tokens) == 1
        and len(tokens[0]) <= 2
    ):
        return BriefSoundDecision(blocked=True, reason="brief_ambiguous_sound")

    return BriefSoundDecision(blocked=False)
