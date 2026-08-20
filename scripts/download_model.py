#!/usr/bin/env python3
"""Download Zipformer Vietnamese ASR model from HuggingFace.

Usage:
    uv run python scripts/download_model.py
    uv run python scripts/download_model.py --model hynt/Zipformer-30M-RNNT-Streaming-6000h
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REQUIRED_FILES = [
    "encoder.int8.onnx",
    "decoder.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
]

DEFAULT_MODEL = "hynt/Zipformer-30M-RNNT-Streaming-6000h"
DEFAULT_DIR = "data/models/asr/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"


def download_model(model_id: str, local_dir: str) -> None:
    try:
        from huggingface_hub import snapshot_download, hf_hub_download
    except ImportError:
        print("ERROR: huggingface_hub not installed.")
        print("Run: uv add huggingface_hub")
        sys.exit(1)

    local_path = Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {model_id} → {local_path}")

    try:
        snapshot_download(
            repo_id=model_id,
            local_dir=str(local_path),
            ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*"],
        )
        print("Download complete!")
    except Exception as exc:
        print(f"snapshot_download failed: {exc}")
        print("Trying individual files...")
        for fname in REQUIRED_FILES:
            try:
                hf_hub_download(
                    repo_id=model_id,
                    filename=fname,
                    local_dir=str(local_path),
                )
                print(f"  Downloaded: {fname}")
            except Exception as e2:
                print(f"  FAILED: {fname} — {e2}")

    # Verify
    print("\nVerifying files:")
    missing = []
    for fname in REQUIRED_FILES:
        path = local_path / fname
        if path.is_file():
            size_mb = path.stat().st_size / 1024 / 1024
            print(f"  ✅ {fname} ({size_mb:.1f} MB)")
        else:
            print(f"  ❌ {fname} — MISSING")
            missing.append(fname)

    if missing:
        print(f"\n⚠️  Missing: {missing}")
        print("The ASR server will start but model will not load.")
        sys.exit(1)
    else:
        print("\nAll required files present! ✅")
        print(f"\nAdd to .env:")
        print(f"ZIPFORMER_MODEL_DIR={local_dir}")


def main():
    parser = argparse.ArgumentParser(description="Download Zipformer ASR model")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dir", default=DEFAULT_DIR)
    args = parser.parse_args()

    # Check HF token
    token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    if not token:
        print("NOTE: No HUGGINGFACE_TOKEN set. Downloading public model...")

    download_model(args.model, args.dir)


if __name__ == "__main__":
    main()
