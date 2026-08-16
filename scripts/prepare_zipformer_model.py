"""Download and verify the pinned sherpa-onnx package for hynt ZipFormer 30M."""

from __future__ import annotations

import hashlib
import io
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

MODEL_ARCHIVE = "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2"
MODEL_DIRNAME = "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"
MODEL_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{MODEL_ARCHIVE}"
MODEL_SHA256 = "da8b637947091829d7ee9eda23da2a4ec7caa399233a3f4e34eb719fb2ea6b9b"
DEFAULT_TARGET = Path("data/models/asr") / MODEL_DIRNAME


def main() -> int:
    target = Path(os.environ.get("ASR_MODEL_DIR", str(DEFAULT_TARGET)))
    if target.name != MODEL_DIRNAME:
        print(f"ASR_MODEL_DIR must end with {MODEL_DIRNAME}: {target}", file=sys.stderr)
        return 1
    destination = target.parent
    if target.is_dir():
        print(f"Model already exists: {target}")
        return 0
    print(f"Downloading pinned model: {MODEL_URL}")
    with urllib.request.urlopen(MODEL_URL, timeout=120) as response:
        archive = response.read()
    digest = hashlib.sha256(archive).hexdigest()
    if digest != MODEL_SHA256:
        print(f"Checksum mismatch: expected {MODEL_SHA256}, got {digest}", file=sys.stderr)
        return 1
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:bz2") as bundle:
        members = bundle.getmembers()
        prefix = f"{MODEL_DIRNAME}/"
        if not members or any(
            member.name.startswith(("/", "\\")) or ".." in Path(member.name).parts or not member.name.startswith(prefix)
            for member in members
        ):
            print("Unsafe model archive layout", file=sys.stderr)
            return 1
        destination.mkdir(parents=True, exist_ok=True)
        bundle.extractall(destination, filter="data")
    required = ("encoder.int8.onnx", "decoder.onnx", "joiner.int8.onnx", "tokens.txt")
    missing = [name for name in required if not (target / name).is_file()]
    if missing:
        print(f"Model extraction incomplete: {missing}", file=sys.stderr)
        return 1
    print(f"Model ready: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
