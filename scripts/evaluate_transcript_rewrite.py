from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.voice.text.rewrite_evaluation import evaluate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate real transcript-rewrite results; no model calls or fake ground truth.")
    parser.add_argument("manifest", type=Path, help="JSON array of annotated rewrite cases")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("manifest must contain a JSON array")
    report = evaluate_dataset(payload)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["hard_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
