#!/usr/bin/env python3
"""Download OpenStreetMap Vietnam extract from Geofabrik (§6).

Usage:
    python scripts/maps/download_osm_vietnam.py [--force] [--output-dir DIR]

Features:
    - Creates output directory if needed
    - Does NOT overwrite existing file unless --force is passed
    - Logs file size and date
    - Fails clearly on download errors
    - Does NOT commit .osm.pbf to git
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GEOFABRIK_URL = "https://download.geofabrik.de/asia/vietnam-latest.osm.pbf"
DEFAULT_OUTPUT_DIR = Path("data/osm/raw")
FILENAME = "vietnam-latest.osm.pbf"
USER_AGENT = "AloSM-OSM-Downloader/1.0"


def download(output_dir: Path, *, force: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / FILENAME

    if target.exists() and not force:
        size_mb = target.stat().st_size / (1024 * 1024)
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(target.stat().st_mtime))
        print(f"[SKIP] {target} already exists ({size_mb:.1f} MB, modified {mtime})")
        print("       Use --force to re-download.")
        return

    print(f"[DOWNLOAD] {GEOFABRIK_URL}")
    print(f"[TARGET]   {target}")

    try:
        request = Request(GEOFABRIK_URL, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=300) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            start = time.monotonic()

            with open(target, "wb") as f:
                while True:
                    chunk = response.read(1024 * 1024)  # 1 MB chunks
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded / total * 100
                        print(
                            f"\r  Progress: {downloaded / (1024 * 1024):.1f} / {total / (1024 * 1024):.1f} MB ({pct:.1f}%)",
                            end="",
                            flush=True,
                        )

            elapsed = time.monotonic() - start
            size_mb = target.stat().st_size / (1024 * 1024)
            print(f"\n[DONE] Downloaded {size_mb:.1f} MB in {elapsed:.1f}s")
            print(f"[DATE] {time.strftime('%Y-%m-%d %H:%M:%S')}")

    except HTTPError as exc:
        print(f"\n[ERROR] HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        sys.exit(1)
    except URLError as exc:
        print(f"\n[ERROR] Connection failed: {exc.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Download failed: {exc}", file=sys.stderr)
        # Clean up partial download
        if target.exists():
            target.unlink()
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Vietnam OSM data from Geofabrik")
    parser.add_argument("--force", action="store_true", help="Force re-download if file exists")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    download(args.output_dir, force=args.force)


if __name__ == "__main__":
    main()
