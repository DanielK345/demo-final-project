SUPPORTED_INTENTS = {"booking", "trip_status", "faq"}


def should_handoff(
    *,
    asr_failed_count: int,
    intent: str | None,
    user_requested_human: bool = False,
    critical_tool_failure: bool = False,
) -> tuple[bool, str | None]:
    if asr_failed_count >= 2:
        return True, "asr_failure"
    if intent is not None and intent not in SUPPORTED_INTENTS:
        return True, "out_of_scope"
    if user_requested_human:
        return True, "user_request"
    if critical_tool_failure:
        return True, "tool_failure"
    return False, None
