#!/usr/bin/env python3
"""Vietnam place search evaluation harness (§43).

Evaluates geocoding quality by running queries against the Maps search API
and comparing results against a ground-truth dataset.

Usage:
    python scripts/maps/evaluate_places.py --dataset datasets/maps/sample_template.csv
    python scripts/maps/evaluate_places.py --dataset datasets/maps/golden_500.csv --api-url http://localhost:8000

Input CSV format (§43):
    query,expected_name,expected_lat,expected_lon,type,slice

Metrics:
    - top1_accuracy: fraction of queries where #1 result matches expected
    - top3_accuracy: fraction of queries where expected is in top 3
    - no_result_rate: fraction with zero candidates
    - false_resolved_rate: fraction auto-resolved incorrectly (should not happen)
    - p50, p95: latency percentiles

Slices: normal, house-number, alley, POI, no-accent, ASR-like, old-new, reverse, boundary
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote as url_quote
from urllib.request import Request, urlopen


def evaluate(dataset_path: str, api_url: str = "http://localhost:8000") -> dict:
    rows = []
    with open(dataset_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("query"):
                rows.append(row)

    if not rows:
        print("[ERROR] No valid rows in dataset", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Evaluating {len(rows)} queries against {api_url}")

    results = {
        "total": len(rows),
        "top1_match": 0,
        "top3_match": 0,
        "no_result": 0,
        "errors": 0,
        "latencies": [],
        "by_slice": {},
    }

    for i, row in enumerate(rows):
        query = row["query"]
        expected_name = row.get("expected_name", "")
        slice_name = row.get("slice", "normal")

        if slice_name not in results["by_slice"]:
            results["by_slice"][slice_name] = {"total": 0, "top1": 0, "top3": 0, "no_result": 0}
        results["by_slice"][slice_name]["total"] += 1

        try:
            url = f"{api_url}/api/v1/places/search?q={url_quote(query)}&limit=5"
            start = time.monotonic()
            req = Request(url, headers={"User-Agent": "AloSM-Eval/1.0"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            elapsed = time.monotonic() - start
            results["latencies"].append(elapsed)

            candidates = data.get("candidates", [])
            if not candidates:
                results["no_result"] += 1
                results["by_slice"][slice_name]["no_result"] += 1
                continue

            names = [c.get("display_name", "").lower() for c in candidates]
            expected_lower = expected_name.lower()

            if expected_lower and expected_lower in names[0]:
                results["top1_match"] += 1
                results["by_slice"][slice_name]["top1"] += 1
            if expected_lower and any(expected_lower in n for n in names[:3]):
                results["top3_match"] += 1
                results["by_slice"][slice_name]["top3"] += 1

        except (URLError, Exception) as exc:
            results["errors"] += 1
            print(f"  [{i + 1}/{len(rows)}] ERROR: {query[:50]} — {exc}", file=sys.stderr)

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(rows)}")

    # Compute metrics
    total = results["total"]
    latencies = sorted(results["latencies"]) if results["latencies"] else [0]

    report = {
        "dataset": dataset_path,
        "total_queries": total,
        "top1_accuracy": results["top1_match"] / total if total else 0,
        "top3_accuracy": results["top3_match"] / total if total else 0,
        "no_result_rate": results["no_result"] / total if total else 0,
        "error_rate": results["errors"] / total if total else 0,
        "p50_seconds": latencies[len(latencies) // 2],
        "p95_seconds": latencies[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0],
        "mean_seconds": statistics.mean(latencies),
        "by_slice": {},
    }

    for sname, sdata in results["by_slice"].items():
        st = sdata["total"]
        report["by_slice"][sname] = {
            "total": st,
            "top1_accuracy": sdata["top1"] / st if st else 0,
            "top3_accuracy": sdata["top3"] / st if st else 0,
            "no_result_rate": sdata["no_result"] / st if st else 0,
        }

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Vietnam place search quality")
    parser.add_argument("--dataset", required=True, help="Path to evaluation CSV")
    parser.add_argument("--api-url", default="http://localhost:8000", help="AloSM API base URL")
    parser.add_argument("--output", help="Output JSON report path")
    args = parser.parse_args()

    report = evaluate(args.dataset, args.api_url)

    print("\n=== Evaluation Report ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[SAVED] {args.output}")


if __name__ == "__main__":
    main()
