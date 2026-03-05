#!/usr/bin/env python3
"""
Download Atlas dataset from Zenodo.

Usage:
    python data/download.py                 # Full dataset
    python data/download.py --sample-only   # Sample only (for quick testing)
    python data/download.py --sample        # Alias for --sample-only
    python data/download.py --check         # Verify existing data integrity
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

CONFIG = {
    "zenodo_doi": "PLACEHOLDER",
    "zenodo_record_url": "https://doi.org/PLACEHOLDER",
    "datasets": {
        "full": [
            {
                "name": "atlas_v31_data_bundle.tar.gz",
                "url": "https://zenodo.org/records/PLACEHOLDER/files/atlas_v31_data_bundle.tar.gz?download=1",
                "sha256": "PLACEHOLDER",
                "target_subdir": "raw",
                "extract": True,
            },
            {
                "name": "atlas_v31_precomputed_bundle.tar.gz",
                "url": "https://zenodo.org/records/PLACEHOLDER/files/atlas_v31_precomputed_bundle.tar.gz?download=1",
                "sha256": "PLACEHOLDER",
                "target_subdir": "processed",
                "extract": True,
            },
        ],
        "sample": [
            {
                "name": "atlas_sample_bundle.zip",
                "url": "https://zenodo.org/records/PLACEHOLDER/files/atlas_sample_bundle.zip?download=1",
                "sha256": "PLACEHOLDER",
                "target_subdir": "sample",
                "extract": True,
            }
        ],
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _print_progress(done: int, total: int) -> None:
    if total <= 0:
        sys.stdout.write(f"\rDownloaded {done / (1024*1024):.1f} MB")
        sys.stdout.flush()
        return
    pct = (done / total) * 100
    bar_len = 30
    fill = int(bar_len * done / total)
    bar = "#" * fill + "-" * (bar_len - fill)
    sys.stdout.write(f"\r[{bar}] {pct:6.2f}% ({done/(1024*1024):.1f}/{total/(1024*1024):.1f} MB)")
    sys.stdout.flush()


def _download(url: str, out_path: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "atlas-downloader/1.0"})
    with urllib.request.urlopen(req) as resp, out_path.open("wb") as f:
        total = int(resp.headers.get("Content-Length", "0") or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            _print_progress(done, total)
    sys.stdout.write("\n")


def _extract(archive_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(target_dir)
        return

    if archive_path.suffix in {".gz", ".tgz"} or archive_path.name.endswith(".tar.gz"):
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(target_dir)
        return

    raise ValueError(f"Unsupported archive format: {archive_path.name}")


def _verify_existing(entries: list[dict]) -> tuple[int, int]:
    ok = 0
    total = 0
    for e in entries:
        total += 1
        target_dir = DATA_DIR / e["target_subdir"]
        marker = target_dir / e["name"]
        if e.get("extract"):
            # For extracted content we verify by presence of target directory and optional checksum marker file.
            if target_dir.exists() and any(target_dir.iterdir()):
                ok += 1
            continue

        if marker.exists() and e["sha256"] != "PLACEHOLDER":
            if _sha256(marker) == e["sha256"]:
                ok += 1
        elif marker.exists():
            ok += 1
    return ok, total


def _is_placeholder_config(entries: list[dict]) -> bool:
    for e in entries:
        if "PLACEHOLDER" in e["url"]:
            return True
    return CONFIG["zenodo_doi"] == "PLACEHOLDER"


def run_download(mode: str) -> int:
    entries = CONFIG["datasets"][mode]
    if _is_placeholder_config(entries):
        if mode == "sample":
            sample_dir = DATA_DIR / "sample"
            if sample_dir.exists() and any(sample_dir.iterdir()):
                print("Zenodo placeholders not configured yet.")
                print("Using bundled local sample dataset in data/sample/.")
                print(f"Sample path: {sample_dir}")
                return 0
        print("Zenodo configuration is not filled yet.")
        print("Please set DOI, URLs, and checksums in data/download.py after publishing on Zenodo.")
        print(json.dumps(CONFIG, indent=2))
        return 2

    downloaded = 0
    skipped = 0

    for e in entries:
        target_dir = DATA_DIR / e["target_subdir"]
        target_dir.mkdir(parents=True, exist_ok=True)

        # Skip if extraction directory already populated
        if e.get("extract") and target_dir.exists() and any(target_dir.iterdir()):
            print(f"[skip] {e['name']} -> {target_dir} already populated")
            skipped += 1
            continue

        with tempfile.TemporaryDirectory(prefix="atlas_dl_") as td:
            tmp_archive = Path(td) / e["name"]
            print(f"[download] {e['name']}")
            try:
                _download(e["url"], tmp_archive)
            except urllib.error.URLError as ex:
                print(f"[error] Download failed for {e['name']}: {ex}")
                return 1

            if e["sha256"] != "PLACEHOLDER":
                digest = _sha256(tmp_archive)
                if digest != e["sha256"]:
                    print(f"[error] SHA-256 mismatch for {e['name']}")
                    print(f"  expected: {e['sha256']}")
                    print(f"  actual:   {digest}")
                    return 1
                print("[ok] checksum verified")
            else:
                print("[warn] checksum placeholder not set; verification skipped")

            if e.get("extract"):
                print(f"[extract] {e['name']} -> {target_dir}")
                _extract(tmp_archive, target_dir)
            else:
                dest_file = target_dir / e["name"]
                shutil.move(str(tmp_archive), str(dest_file))

            downloaded += 1

    print("\nDownload summary")
    print(f"  mode: {mode}")
    print(f"  downloaded: {downloaded}")
    print(f"  skipped: {skipped}")
    print(f"  data root: {DATA_DIR}")
    return 0


def run_check(sample_only: bool) -> int:
    modes = ["sample"] if sample_only else ["sample", "full"]
    entries = []
    for m in modes:
        entries.extend(CONFIG["datasets"][m])

    ok, total = _verify_existing(entries)
    print("Integrity check")
    print(f"  checked: {total}")
    print(f"  passing: {ok}")
    print(f"  failing: {total - ok}")
    return 0 if ok == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Atlas data from Zenodo")
    parser.add_argument("--sample-only", action="store_true", help="Download sample dataset only")
    parser.add_argument("--sample", action="store_true", help="Alias for --sample-only")
    parser.add_argument("--check", action="store_true", help="Verify existing data integrity")
    args = parser.parse_args()

    sample_only = bool(args.sample_only or args.sample)

    if args.check:
        return run_check(sample_only=sample_only)

    return run_download(mode="sample" if sample_only else "full")


if __name__ == "__main__":
    raise SystemExit(main())
