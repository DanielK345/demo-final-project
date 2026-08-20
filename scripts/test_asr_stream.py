#!/usr/bin/env python3
"""Test ASR WebSocket streaming with a WAV file.

Usage:
    uv run python scripts/test_asr_stream.py path/to/audio.wav
    uv run python scripts/test_asr_stream.py path/to/audio.wav --url ws://localhost:9000/v1/stt
"""
from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
import time
import wave
from pathlib import Path


async def stream_wav(wav_path: str, url: str, chunk_ms: int = 100) -> None:
    """Stream a WAV file to the ASR WebSocket server and print transcripts."""
    try:
        import websockets
    except ImportError:
        print("ERROR: websockets not installed. Run: uv add websockets")
        sys.exit(1)

    path = Path(wav_path)
    if not path.is_file():
        print(f"ERROR: File not found: {wav_path}")
        sys.exit(1)

    with wave.open(str(path), "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        n_frames = wf.getnframes()
        audio_data = wf.readframes(n_frames)

    print(f"Audio: {path.name}")
    print(f"  Sample rate: {sample_rate} Hz")
    print(f"  Channels:    {channels}")
    print(f"  Duration:    {n_frames / sample_rate:.2f}s")
    print(f"ASR URL: {url}")
    print("-" * 60)

    chunk_frames = int(sample_rate * chunk_ms / 1000)
    chunk_bytes = chunk_frames * channels * 2  # int16

    t_start = time.perf_counter()
    first_partial_t: float | None = None
    first_final_t: float | None = None

    async with websockets.connect(url, open_timeout=10) as ws:
        # Handshake
        await ws.send(json.dumps({
            "type": "start",
            "sample_rate": sample_rate,
            "channels": channels,
            "language": "vi",
        }))

        # Stream audio chunks
        offset = 0
        while offset < len(audio_data):
            chunk = audio_data[offset:offset + chunk_bytes]
            offset += chunk_bytes
            await ws.send(chunk)
            await asyncio.sleep(chunk_ms / 1000)  # real-time simulation

        # Signal end
        await ws.send(json.dumps({"type": "finish"}))

        # Receive transcripts
        async for raw in ws:
            if isinstance(raw, bytes):
                continue
            msg = json.loads(raw)
            t_now = time.perf_counter()
            elapsed = t_now - t_start

            if msg["type"] == "interim":
                if first_partial_t is None:
                    first_partial_t = elapsed
                    print(f"[{elapsed:.3f}s] PARTIAL (first): {msg['text']}")
                else:
                    print(f"[{elapsed:.3f}s] PARTIAL: {msg['text']}")

            elif msg["type"] == "final":
                if first_final_t is None:
                    first_final_t = elapsed
                print(f"[{elapsed:.3f}s] FINAL: {msg['text']}")

            elif msg["type"] in ("closed", "error"):
                break

    t_end = time.perf_counter()
    print("-" * 60)
    print(f"Total time:         {t_end - t_start:.3f}s")
    if first_partial_t:
        print(f"First partial:      {first_partial_t:.3f}s")
    if first_final_t:
        print(f"First final:        {first_final_t:.3f}s")
    audio_dur = n_frames / sample_rate
    rtf = (t_end - t_start) / audio_dur if audio_dur > 0 else 0
    print(f"RTF:                {rtf:.3f}x")


def main():
    parser = argparse.ArgumentParser(description="Test ASR WebSocket streaming")
    parser.add_argument("wav", help="Path to WAV file")
    parser.add_argument("--url", default="ws://localhost:9000/v1/stt", help="ASR WebSocket URL")
    parser.add_argument("--chunk-ms", type=int, default=100, help="Chunk size in ms (default: 100)")
    args = parser.parse_args()
    asyncio.run(stream_wav(args.wav, args.url, args.chunk_ms))


if __name__ == "__main__":
    main()
