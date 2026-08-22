"""Aggregate native LiveKit events and AloSM RTC smoke results.

This is intentionally glue code: LiveKit owns event generation, per-turn metrics,
usage accounting, Room lifecycle, and agent dispatch. The script only computes
project-level percentiles, rates, and AloSM booking invariants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from collections import Counter, defaultdict
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

LATENCY_FIELDS_SECONDS = (
    "transcription_delay",
    "end_of_turn_delay",
    "on_user_turn_completed_delay",
    "llm_node_ttft",
    "tts_node_ttfb",
    "playback_latency",
    "e2e_latency",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSON objects with a precise error when an artifact is malformed."""

    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(row)
    return rows


def percentile(values: list[float], fraction: float) -> float | None:
    """Return a nearest-rank percentile, suitable for release reports."""

    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def summarize_values(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "p50": _rounded(percentile(values, 0.50)),
        "p90": _rounded(percentile(values, 0.90)),
        "p95": _rounded(percentile(values, 0.95)),
        "worst": _rounded(max(values) if values else None),
    }


def _rounded(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _safe_number(value: object) -> float | None:
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    return None


def _smoke_segment_values(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    segments: dict[str, list[float]] = defaultdict(list)
    pairs = {
        "credential_issue_ms": (None, "credentials_issued"),
        "room_connect_ms": ("credentials_issued", "room_connected"),
        "agent_join_after_room_ms": ("room_connected", "agent_joined"),
        "first_audio_after_join_ms": ("agent_joined", "first_agent_audio"),
        "booking_state_after_join_ms": ("agent_joined", "booking_state_received"),
        "greeting_complete_after_join_ms": ("agent_joined", "greeting_completed"),
        "booking_completion_after_join_ms": ("agent_joined", "booking_completed"),
    }
    for row in rows:
        timings = row.get("timings_ms")
        if not isinstance(timings, dict):
            continue
        for name, (start_name, end_name) in pairs.items():
            end_value = _safe_number(timings.get(end_name))
            start_value = 0.0 if start_name is None else _safe_number(timings.get(start_name))
            if end_value is not None and start_value is not None and end_value >= start_value:
                segments[name].append(end_value - start_value)
    return segments


def _timestamp_ms(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000
    except ValueError:
        return None


def cross_boundary_latencies(smoke_rows: list[dict[str, Any]], log_paths: list[Path]) -> dict[str, list[float]]:
    """Correlate RTC attempts and worker logs by opaque application session ID."""

    worker_started_by_session: dict[str, float] = {}
    for path in log_paths:
        for event in load_jsonl(path):
            if event.get("event") != "worker_milestone" or event.get("milestone") != "job_entry":
                continue
            app_session_id = str(event.get("app_session_id") or "")
            timestamp = _timestamp_ms(event.get("timestamp"))
            if app_session_id and timestamp is not None:
                worker_started_by_session[app_session_id] = timestamp
            break

    values: dict[str, list[float]] = defaultdict(list)
    for row in smoke_rows:
        app_session_id = str(row.get("app_session_id") or "")
        attempt_started = _timestamp_ms(row.get("started_at"))
        timings = row.get("timings_ms")
        worker_started = worker_started_by_session.get(app_session_id)
        if attempt_started is None or worker_started is None or not isinstance(timings, dict):
            continue
        room_connected = _safe_number(timings.get("room_connected"))
        agent_joined = _safe_number(timings.get("agent_joined"))
        if room_connected is not None:
            duration = worker_started - (attempt_started + room_connected)
            if duration >= 0:
                values["room_to_worker_job_entry_ms"].append(duration)
        if agent_joined is not None:
            duration = attempt_started + agent_joined - worker_started
            if duration >= 0:
                values["worker_job_entry_to_agent_join_ms"].append(duration)
    return values


def check_business_invariants(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Check only invariants observable from structured AloSM booking state."""

    violations: list[dict[str, object]] = []
    session_booking_ids: dict[str, set[str]] = defaultdict(set)
    booking_sessions: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        run_number = row.get("run_number")
        app_session_id = str(row.get("app_session_id", ""))
        checks = row.get("checks") if isinstance(row.get("checks"), dict) else {}
        booking_ids = row.get("booking_ids")
        ids = [item for item in booking_ids if isinstance(item, str)] if isinstance(booking_ids, list) else []
        if ids and row.get("confirmation_status_at_booking") != "confirmed":
            violations.append({"type": "booking_without_confirmation", "run_number": run_number})
        if len(set(ids)) > 1:
            violations.append({"type": "multiple_booking_ids_in_attempt", "run_number": run_number})
        for booking_id in ids:
            session_booking_ids[app_session_id].add(booking_id)
            booking_sessions[booking_id].add(app_session_id)
        # Schema v2 adds authoritative Supabase row checks. Keep historical v1
        # artifacts reproducible instead of retroactively failing old baselines.
        if row.get("booking_enabled") and str(row.get("schema_version")) == "2":
            durable_check_names = (
                "durable_session_exists",
                "durable_session_ended",
                "durable_session_booking_matches",
                "durable_state_advanced",
                "durable_quote_matches",
                "durable_booking_matches",
            )
            failed_checks = [name for name in durable_check_names if checks.get(name) is not True]
            if failed_checks:
                violations.append(
                    {
                        "type": "durable_booking_verification_failed",
                        "run_number": run_number,
                        "app_session_id": app_session_id,
                        "failed_checks": failed_checks,
                    }
                )

    for app_session_id, booking_ids in session_booking_ids.items():
        if app_session_id and len(booking_ids) > 1:
            violations.append({"type": "duplicate_booking_for_session", "app_session_id": app_session_id})
    for booking_id, app_session_ids in booking_sessions.items():
        if booking_id and len(app_session_ids) > 1:
            violations.append({"type": "booking_id_cross_session_leakage", "booking_id": booking_id})

    return {
        "passed": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }


def aggregate_native_logs(log_paths: list[Path]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    metric_values: dict[str, list[float]] = defaultdict(list)
    error_types: Counter[str] = Counter()
    failure_sources: Counter[str] = Counter()
    tool_statuses: Counter[str] = Counter()
    tool_durations: list[float] = []
    agent_task_durations: list[float] = []
    configurations: dict[str, dict[str, Any]] = {}
    usage_totals: dict[tuple[str, str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    speaking_turns = 0
    final_transcripts = 0
    transcription_timeouts = 0
    sessions_with_first_turn = 0
    sessions_with_speech = 0

    for path in log_paths:
        events = load_jsonl(path)
        session_spoke = False
        session_final = False
        last_usage: list[dict[str, Any]] = []
        for event in events:
            event_name = event.get("event")
            if event_name == "session_configured":
                config = {
                    key: value
                    for key, value in event.items()
                    if key
                    not in {
                        "schema_version",
                        "timestamp",
                        "elapsed_ms",
                        "event",
                        "app_session_id",
                        "call_id",
                        "room_name",
                    }
                }
                fingerprint = hashlib.sha256(
                    json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()[:16]
                configurations[fingerprint] = config
            elif event_name == "conversation_item_added":
                metrics = event.get("metrics")
                if isinstance(metrics, dict):
                    for field in LATENCY_FIELDS_SECONDS:
                        number = _safe_number(metrics.get(field))
                        if number is not None:
                            metric_values[f"{field}_ms"].append(number * 1000)
            elif event_name == "worker_milestone":
                milestone = event.get("milestone")
                duration = _safe_number(event.get("duration_ms"))
                elapsed = _safe_number(event.get("elapsed_ms"))
                if isinstance(milestone, str) and duration is not None:
                    metric_values[f"worker_{milestone}_duration_ms"].append(duration)
                if isinstance(milestone, str) and elapsed is not None:
                    metric_values[f"worker_{milestone}_elapsed_ms"].append(elapsed)
            elif event_name == "user_state_changed" and event.get("new_state") == "speaking":
                speaking_turns += 1
                session_spoke = True
            elif event_name == "user_input_transcribed" and event.get("is_final") is True:
                final_transcripts += 1
                session_final = True
            elif event_name == "user_transcription_timeout":
                transcription_timeouts += 1
            elif event_name == "error":
                error_types[str(event.get("error_type") or "unknown")] += 1
                failure_sources[str(event.get("source_type") or "unknown")] += 1
            elif event_name == "function_tools_executed":
                tools = event.get("tools")
                if isinstance(tools, list):
                    for tool in tools:
                        if isinstance(tool, dict):
                            tool_statuses[str(tool.get("status") or "unknown")] += 1
            elif event_name == "tool_execution_updated":
                duration = _safe_number(event.get("duration_ms"))
                if duration is not None:
                    # A tool that awaits AgentTask is the whole multi-turn
                    # sub-conversation, not backend I/O. Report it separately so
                    # it cannot distort search/quote/booking tool percentiles.
                    if event.get("tool_name") == "start_booking":
                        agent_task_durations.append(duration)
                    else:
                        tool_durations.append(duration)
            elif event_name == "session_usage_updated" and isinstance(event.get("model_usage"), list):
                last_usage = [item for item in event["model_usage"] if isinstance(item, dict)]

        sessions_with_speech += int(session_spoke)
        sessions_with_first_turn += int(session_spoke and session_final)
        for usage in last_usage:
            key = (
                str(usage.get("type") or "unknown"),
                str(usage.get("provider") or "unknown"),
                str(usage.get("model") or "unknown"),
            )
            for field, raw_value in usage.items():
                number = _safe_number(raw_value)
                if field not in {"type", "provider", "model"} and number is not None:
                    usage_totals[key][field] += number

    latency = {field: summarize_values(values) for field, values in sorted(metric_values.items())}
    latency["tool_duration_ms"] = summarize_values(tool_durations)
    latency["agent_task_duration_ms"] = summarize_values(agent_task_durations)
    unmatched_speech_episodes = max(0, speaking_turns - final_transcripts)
    failures = {
        "session_count": len(log_paths),
        "error_event_count": sum(error_types.values()),
        "errors_by_type": dict(error_types.most_common()),
        "errors_by_source": dict(failure_sources.most_common()),
        "tool_statuses": dict(tool_statuses.most_common()),
        "speaking_turns": speaking_turns,
        "final_transcripts": final_transcripts,
        "transcription_timeout_count": transcription_timeouts,
        # A native state transition is a speech episode, not necessarily a complete
        # semantic turn. Keep this diagnostic explicitly named; a release-grade
        # no-final rate requires a controlled audio manifest and turn correlation.
        "unmatched_speech_episodes": unmatched_speech_episodes,
        "observed_speech_episode_no_final_rate": _rate(unmatched_speech_episodes, speaking_turns),
        "sessions_with_speech": sessions_with_speech,
        "session_transcript_coverage_rate": _rate(sessions_with_first_turn, sessions_with_speech),
    }
    usage_summary = [
        {
            "type": key[0],
            "provider": key[1],
            "model": key[2],
            **{field: round(value, 6) for field, value in sorted(totals.items())},
        }
        for key, totals in sorted(usage_totals.items())
    ]
    config_summary = [{"fingerprint": fingerprint, **config} for fingerprint, config in sorted(configurations.items())]
    return latency, failures, [{"configurations": config_summary}, {"usage": usage_summary}]


def aggregate_smoke(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    attempts = len(rows)
    passed = sum(row.get("status") == "passed" for row in rows)
    checks = Counter()
    applicable = Counter()
    failure_stages = Counter(str(row.get("failure_stage") or "none") for row in rows if row.get("status") != "passed")
    input_modes = Counter(str(row.get("input_mode") or "unspecified") for row in rows)
    for row in rows:
        row_checks = row.get("checks")
        if not isinstance(row_checks, dict):
            continue
        for name, value in row_checks.items():
            if isinstance(value, bool):
                applicable[str(name)] += 1
                checks[str(name)] += int(value)
    summary = {
        "attempt_count": attempts,
        "passed_count": passed,
        "success_rate": _rate(passed, attempts),
        "check_rates": {
            name: {"passed": checks[name], "applicable": count, "rate": _rate(checks[name], count)}
            for name, count in sorted(applicable.items())
        },
        "failure_stages": dict(failure_stages.most_common()),
        "input_modes": dict(input_modes),
    }
    latency = {name: summarize_values(values) for name, values in sorted(_smoke_segment_values(rows).items())}
    return summary, latency


def _package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _report_markdown(
    *,
    dataset_version: str,
    run_id: str,
    smoke: dict[str, Any],
    failures: dict[str, Any],
    latency: dict[str, Any],
    invariants: dict[str, Any],
) -> str:
    lines = [
        "# LiveKit Phase 4 evaluation report",
        "",
        f"- Dataset: `{dataset_version}`",
        f"- Run: `{run_id}`",
        f"- Generated: `{datetime.now(tz=UTC).isoformat(timespec='seconds')}`",
        "",
        "## Connection smoke",
        "",
        f"- Attempts: {smoke['attempt_count']}",
        f"- Passed: {smoke['passed_count']}",
        f"- Success rate: {smoke['success_rate']}",
        f"- Failure stages: `{json.dumps(smoke['failure_stages'], ensure_ascii=False)}`",
        f"- Input modes: `{json.dumps(smoke['input_modes'], ensure_ascii=False)}`",
        "",
        "## Native LiveKit reliability",
        "",
        f"- Agent-session logs: {failures['session_count']}",
        (
            "- STT transcript coverage: not applicable (LiveKit text-input smoke)"
            if set(smoke["input_modes"]) == {"livekit_text"}
            else f"- Session transcript coverage: {failures['session_transcript_coverage_rate']}"
        ),
        (
            "- Speech-episode no-final rate: not applicable (no audio input)"
            if set(smoke["input_modes"]) == {"livekit_text"}
            else "- Observed speech-episode no-final rate (diagnostic only): "
            f"{failures['observed_speech_episode_no_final_rate']}"
        ),
        f"- Native error events: {failures['error_event_count']}",
        f"- Native transcription timeout events: {failures['transcription_timeout_count']}",
        "",
        "## Latency (milliseconds)",
        "",
        "| Metric | Count | p50 | p90 | p95 | Worst |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, values in sorted(latency.items()):
        lines.append(
            f"| `{name}` | {values['count']} | {values['p50']} | {values['p90']} | "
            f"{values['p95']} | {values['worst']} |"
        )
    lines.extend(
        [
            "",
            "## Business invariants",
            "",
            f"- Passed: {invariants['passed']}",
            f"- Violations: {invariants['violation_count']}",
            "",
            "> This report aggregates native LiveKit events and structured AloSM state. "
            "It does not infer business state from transcripts.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_report(
    *,
    log_dir: Path,
    smoke_results: Path | None,
    output_dir: Path,
    dataset_version: str,
    run_id: str,
) -> Path:
    log_paths = sorted(log_dir.glob("*.jsonl")) if log_dir.exists() else []
    smoke_rows = load_jsonl(smoke_results) if smoke_results else []
    native_latency, failures, native_metadata = aggregate_native_logs(log_paths)
    smoke_summary, smoke_latency = aggregate_smoke(smoke_rows)
    cross_boundary = {
        name: summarize_values(values)
        for name, values in sorted(cross_boundary_latencies(smoke_rows, log_paths).items())
    }
    invariants = check_business_invariants(smoke_rows)
    latency_summary = {**native_latency, **smoke_latency, **cross_boundary}
    config_summary = native_metadata[0]["configurations"]
    usage_summary = native_metadata[1]["usage"]

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "config.json",
        {
            "dataset_version": dataset_version,
            "run_id": run_id,
            "native_configurations": config_summary,
            "input_log_count": len(log_paths),
            "smoke_results": smoke_results.name if smoke_results else None,
        },
    )
    _write_json(
        output_dir / "environment.json",
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "livekit_agents": _package_version("livekit-agents"),
            "livekit": _package_version("livekit"),
        },
    )
    _write_json(output_dir / "latency-summary.json", latency_summary)
    _write_json(output_dir / "failure-summary.json", {**failures, "smoke": smoke_summary})
    _write_json(output_dir / "cost-summary.json", {"usage": usage_summary, "cost": None})
    _write_json(output_dir / "business-invariants.json", invariants)
    (output_dir / "report.md").write_text(
        _report_markdown(
            dataset_version=dataset_version,
            run_id=run_id,
            smoke=smoke_summary,
            failures=failures,
            latency=latency_summary,
            invariants=invariants,
        ),
        encoding="utf-8",
    )
    return output_dir


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    now = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", type=Path, default=Path("logs/livekit"))
    parser.add_argument("--smoke-results", type=Path)
    parser.add_argument("--dataset-version", default="phase4a-v1")
    parser.add_argument("--run-id", default=now)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.output_dir is None:
        args.output_dir = Path("reports") / "voice-evaluation" / args.dataset_version / args.run_id
    return args


if __name__ == "__main__":
    args = _parse_args()
    result_dir = generate_report(
        log_dir=args.log_dir,
        smoke_results=args.smoke_results,
        output_dir=args.output_dir,
        dataset_version=args.dataset_version,
        run_id=args.run_id,
    )
    print(f"LIVEKIT_EVALUATION_REPORT={result_dir}")
    invariant_result = json.loads((result_dir / "business-invariants.json").read_text(encoding="utf-8"))
    if not invariant_result.get("passed", False):
        print(f"LIVEKIT_BUSINESS_INVARIANTS=FAILED COUNT={invariant_result.get('violation_count', 0)}")
        raise SystemExit(2)
    print("LIVEKIT_BUSINESS_INVARIANTS=PASS")
