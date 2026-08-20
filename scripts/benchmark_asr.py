#!/usr/bin/env python3
"""Benchmark ASR server with concurrent sessions.

Usage:
    uv run python scripts/benchmark_asr.py path/to/audio.wav
    uv run python scripts/benchmark_asr.py path/to/audio.wav --sessions 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import wave
from pathlib import Path
from statistics import mean, stdev


async def run_session(wav_data: bytes, sample_rate: int, url: str, session_id: int) -> dict:
    try:
        import websockets
    except ImportError:
        print("ERROR: install websockets")
        sys.exit(1)

    t_start = time.perf_counter()
    first_partial = None
    first_final = None
    finals = []

    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            await ws.send(json.dumps({"type": "start", "sample_rate": sample_rate, "language": "vi"}))
            chunk = 3200  # 100ms at 16kHz
            for i in range(0, len(wav_data), chunk):
                await ws.send(wav_data[i:i + chunk])
                await asyncio.sleep(0.1)
            await ws.send(json.dumps({"type": "finish"}))
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue
                msg = json.loads(raw)
                t = time.perf_counter() - t_start
                if msg["type"] == "interim" and first_partial is None:
                    first_partial = t
                elif msg["type"] == "final":
                    if first_final is None:
                        first_final = t
                    finals.append(msg.get("text", ""))
                elif msg["type"] in ("closed", "error"):
                    break
    except Exception as exc:
        return {"session": session_id, "error": str(exc)}

    return {
        "session": session_id,
        "total_s": time.perf_counter() - t_start,
        "first_partial_s": first_partial,
        "first_final_s": first_final,
        "transcripts": finals,
    }


async def benchmark(wav_path: str, url: str, n_sessions: int) -> None:
    with wave.open(wav_path, "rb") as wf:
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        wav_data = wf.readframes(n_frames)

    audio_dur = n_frames / sample_rate
    print(f"Audio: {wav_path}  ({audio_dur:.2f}s)")
    print(f"Sessions: {n_sessions}  URL: {url}")
    print("-" * 60)

    t_start = time.perf_counter()
    results = await asyncio.gather(*[
        run_session(wav_data, sample_rate, url, i)
        for i in range(n_sessions)
    ])
    total_wall = time.perf_counter() - t_start

    ok = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]

    if ok:
        latencies = [r["total_s"] for r in ok if r.get("total_s")]
        partials = [r["first_partial_s"] for r in ok if r.get("first_partial_s")]
        finals = [r["first_final_s"] for r in ok if r.get("first_final_s")]
        print(f"Success:           {len(ok)}/{n_sessions}")
        print(f"Wall time:         {total_wall:.3f}s")
        print(f"Session total avg: {mean(latencies):.3f}s ± {stdev(latencies) if len(latencies) > 1 else 0:.3f}s")
        if partials:
            print(f"First partial avg: {mean(partials):.3f}s")
        if finals:
            print(f"First final avg:   {mean(finals):.3f}s")
        print(f"RTF (per session): {mean(latencies) / audio_dur:.3f}x")
    if errors:
        print(f"Errors ({len(errors)}):")
        for r in errors:
            print(f"  Session {r['session']}: {r['error']}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark ASR streaming")
    parser.add_argument("wav", help="WAV file path")
    parser.add_argument("--url", default="ws://localhost:9000/v1/stt")
    parser.add_argument("--sessions", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(benchmark(args.wav, args.url, args.sessions))


if __name__ == "__main__":
    main()
