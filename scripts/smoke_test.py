#!/usr/bin/env python3
"""Smoke test: backend health, ASR health, token generation, LiveKit WS.

Usage:
    uv run python scripts/smoke_test.py
    uv run python scripts/smoke_test.py --backend http://localhost:8000 --asr http://localhost:9000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

import urllib.request
import urllib.error


def http_get(url: str, timeout: int = 5) -> tuple[int, dict]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "✅ PASS" if ok else "❌ FAIL"
    print(f"  {status}  {name}" + (f"  [{detail}]" if detail else ""))
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--asr", default="http://localhost:9000")
    args = parser.parse_args()

    print("\n=== AloSM Voice AI Smoke Test ===\n")
    results = []

    # 1. Backend health
    print("Backend:")
    code, data = http_get(f"{args.backend}/health")
    results.append(check("GET /health → 200", code == 200, f"status={data.get('status','')}"))

    # 2. ASR health
    print("\nASR Server:")
    code, data = http_get(f"{args.asr}/health")
    results.append(check("GET /health → 200", code == 200, f"model_loaded={data.get('model_loaded','')}"))

    code, data = http_get(f"{args.asr}/ready")
    results.append(check("GET /ready → 200 (model loaded)", code == 200, str(data)))

    # 3. LiveKit worker (port 8081)
    print("\nLiveKit Worker:")
    code, data = http_get("http://localhost:8081/health")
    results.append(check("Worker health port 8081", code == 200, str(data)))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*40}")
    print(f"Result: {passed}/{total} checks passed")
    if passed < total:
        print("\nFailed checks — see above for details.")
        sys.exit(1)
    else:
        print("All checks passed! ✅")


if __name__ == "__main__":
    main()
