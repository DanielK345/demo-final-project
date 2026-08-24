import json
from pathlib import Path

from scripts.aggregate_livekit_evaluation import (
    aggregate_native_logs,
    aggregate_smoke,
    check_business_invariants,
    cross_boundary_latencies,
    generate_report,
    percentile,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_percentile_uses_nearest_rank() -> None:
    values = [10.0, 20.0, 30.0, 40.0]

    assert percentile(values, 0.50) == 20.0
    assert percentile(values, 0.90) == 40.0
    assert percentile([], 0.95) is None


def test_aggregates_native_metrics_and_only_final_usage_snapshot(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "call-1.jsonl"
    _write_jsonl(
        log_path,
        [
            {
                "event": "session_configured",
                "call_id": "call-1",
                "llm_model": "model-a",
            },
            {
                "event": "worker_milestone",
                "milestone": "state_restore_completed",
                "duration_ms": 12.5,
                "elapsed_ms": 13.0,
            },
            {"event": "user_state_changed", "new_state": "speaking"},
            {"event": "user_input_transcribed", "is_final": True},
            {
                "event": "conversation_item_added",
                "role": "assistant",
                "metrics": {"llm_node_ttft": 1.25, "e2e_latency": 2.5},
                "text": "private transcript must be ignored",
            },
            {
                "event": "session_usage_updated",
                "model_usage": [
                    {
                        "type": "llm_usage",
                        "provider": "test",
                        "model": "model-a",
                        "input_tokens": 10,
                    }
                ],
            },
            {
                "event": "session_usage_updated",
                "model_usage": [
                    {
                        "type": "llm_usage",
                        "provider": "test",
                        "model": "model-a",
                        "input_tokens": 15,
                        "output_tokens": 4,
                    }
                ],
            },
        ],
    )

    latency, failures, metadata = aggregate_native_logs([log_path])

    assert latency["llm_node_ttft_ms"]["p50"] == 1250.0
    assert latency["e2e_latency_ms"]["p95"] == 2500.0
    assert latency["worker_state_restore_completed_duration_ms"]["p50"] == 12.5
    assert failures["session_transcript_coverage_rate"] == 1.0
    usage = metadata[1]["usage"]
    assert usage[0]["input_tokens"] == 15.0
    assert usage[0]["output_tokens"] == 4.0


def test_correlates_room_attempt_with_worker_job_entry(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "call-1.jsonl"
    _write_jsonl(
        log_path,
        [
            {
                "event": "worker_milestone",
                "milestone": "job_entry",
                "app_session_id": "session-1",
                "timestamp": "2026-08-20T10:00:04.000+00:00",
            }
        ],
    )
    smoke_rows = [
        {
            "app_session_id": "session-1",
            "started_at": "2026-08-20T10:00:00.000+00:00",
            "timings_ms": {"room_connected": 1000.0, "agent_joined": 5500.0},
        }
    ]

    values = cross_boundary_latencies(smoke_rows, [log_path])

    assert values["room_to_worker_job_entry_ms"] == [3000.0]
    assert values["worker_job_entry_to_agent_join_ms"] == [1500.0]


def test_smoke_rates_and_business_invariants() -> None:
    rows = [
        {
            "run_number": 1,
            "status": "passed",
            "input_mode": "livekit_text",
            "app_session_id": "session-1",
            "booking_ids": ["booking-1"],
            "confirmation_status_at_booking": "confirmed",
            "checks": {"room_connected": True, "agent_joined": True},
            "timings_ms": {
                "credentials_issued": 10.0,
                "room_connected": 110.0,
                "agent_joined": 310.0,
            },
        },
        {
            "run_number": 2,
            "status": "failed",
            "failure_stage": "agent_join",
            "app_session_id": "session-2",
            "booking_ids": [],
            "checks": {"room_connected": True},
            "timings_ms": {"credentials_issued": 20.0, "room_connected": 220.0},
        },
    ]

    summary, latency = aggregate_smoke(rows)
    invariants = check_business_invariants(rows)

    assert summary["success_rate"] == 0.5
    assert summary["failure_stages"] == {"agent_join": 1}
    assert summary["input_modes"] == {"livekit_text": 1, "unspecified": 1}
    assert latency["room_connect_ms"]["p95"] == 200.0
    assert invariants == {"passed": True, "violation_count": 0, "violations": []}


def test_business_invariants_detect_confirmation_duplicate_and_cross_session() -> None:
    rows = [
        {
            "run_number": 1,
            "app_session_id": "session-1",
            "booking_ids": ["booking-shared", "booking-other"],
            "confirmation_status_at_booking": "awaiting",
        },
        {
            "run_number": 2,
            "app_session_id": "session-2",
            "booking_ids": ["booking-shared"],
            "confirmation_status_at_booking": "confirmed",
        },
    ]

    invariants = check_business_invariants(rows)
    violation_types = {item["type"] for item in invariants["violations"]}

    assert invariants["passed"] is False
    assert violation_types == {
        "booking_without_confirmation",
        "multiple_booking_ids_in_attempt",
        "duplicate_booking_for_session",
        "booking_id_cross_session_leakage",
    }


def test_business_invariants_require_db_evidence_for_booking_smoke() -> None:
    invariants = check_business_invariants(
        [
            {
                "schema_version": "2",
                "run_number": 1,
                "booking_enabled": True,
                "app_session_id": "session-1",
                "booking_ids": ["booking-1"],
                "confirmation_status_at_booking": "confirmed",
                "checks": {"durable_session_exists": True},
            }
        ]
    )

    assert invariants["passed"] is False
    assert invariants["violations"][0]["type"] == "durable_booking_verification_failed"
    assert "durable_booking_matches" in invariants["violations"][0]["failed_checks"]


def test_generate_report_does_not_copy_transcripts(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    _write_jsonl(
        log_dir / "call.jsonl",
        [
            {"event": "session_configured", "llm_model": "model-a"},
            {
                "event": "conversation_item_added",
                "role": "user",
                "text": "địa chỉ riêng tư",
                "metrics": {"transcription_delay": 0.5},
            },
        ],
    )
    smoke_path = tmp_path / "smoke.jsonl"
    _write_jsonl(
        smoke_path,
        [
            {
                "run_number": 1,
                "status": "passed",
                "input_mode": "livekit_text",
                "app_session_id": "session-1",
                "booking_ids": [],
                "checks": {"room_connected": True},
            }
        ],
    )
    output_dir = tmp_path / "report"

    generate_report(
        log_dir=log_dir,
        smoke_results=smoke_path,
        output_dir=output_dir,
        dataset_version="dataset-v1",
        run_id="run-1",
    )

    rendered = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file())
    assert "địa chỉ riêng tư" not in rendered
    assert (output_dir / "latency-summary.json").exists()
    assert (output_dir / "business-invariants.json").exists()
    assert "STT transcript coverage: not applicable" in (output_dir / "report.md").read_text(encoding="utf-8")


def test_agent_task_duration_does_not_pollute_backend_tool_latency(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "call-1.jsonl"
    _write_jsonl(
        log_path,
        [
            {
                "event": "tool_execution_updated",
                "tool_name": "start_booking",
                "duration_ms": 45_000,
            },
            {
                "event": "tool_execution_updated",
                "tool_name": "search_place",
                "duration_ms": 8,
            },
        ],
    )

    latency, _, _ = aggregate_native_logs([log_path])

    assert latency["agent_task_duration_ms"]["p50"] == 45_000
    assert latency["tool_duration_ms"]["p50"] == 8
