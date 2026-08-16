from src.voice.text.rewrite_evaluation import evaluate_dataset


def test_rewrite_evaluator_passes_preserved_semantics_entities_and_placeholders():
    report = evaluate_dataset([
        {
            "case_id": "safe",
            "raw_transcript": "tôi không hủy chuyến <PHONE_1>",
            "ground_truth": "tôi không hủy chuyến <PHONE_1>",
            "rewritten_transcript": "Tôi không hủy chuyến <PHONE_1>.",
            "entities": [{"type": "phone", "value": "<PHONE_1>"}],
            "latency_ms": 120,
            "cost_usd": 0.001,
        }
    ])
    assert report["hard_gate_passed"] is True
    assert report["semantic_flip_count"] == 0
    assert report["pii_placeholder_violation_count"] == 0
    assert report["entity_error_rate"] == 0


def test_rewrite_evaluator_fails_negation_flip_and_placeholder_deletion():
    report = evaluate_dataset([
        {
            "case_id": "unsafe",
            "raw_transcript": "tôi không đặt xe <PHONE_1>",
            "ground_truth": "tôi không đặt xe <PHONE_1>",
            "rewritten_transcript": "Tôi đặt xe.",
            "entities": [{"type": "phone", "value": "<PHONE_1>"}],
        }
    ])
    assert report["hard_gate_passed"] is False
    assert report["semantic_flip_count"] == 1
    assert report["pii_placeholder_violation_count"] == 1
    assert report["entity_error_rate"] == 1
