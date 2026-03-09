#!/usr/bin/env python3
"""
E: drive organizer – report and optionally clean junk, duplicates, and organize images/files.

Usage:
  python organize_drive.py --drive E:\\          # Report only (default)
  python organize_drive.py --drive E:\\ --execute   # Apply cleanup and organization (use with care)
  python organize_drive.py --drive E:\\ --report-junk --report-dupes --report-images
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# --- Junk patterns (relative to any folder) ---
JUNK_NAMES = {
    "Thumbs.db",
    "desktop.ini",
    ".DS_Store",
    ".Spotlight-V100",
    ".Trashes",
    "ehthumbs.db",
    "Desktop.ini",
}
JUNK_EXTENSIONS = {
    ".tmp", ".temp", ".bak", ".old", ".log", ".cache",
    ".crdownload", ".part", ".!ut", ".download",
    "~", ".swp", ".swo",
}
JUNK_FOLDER_NAMES = {
    "__MACOSX",
    ".Trash",
    "Temp", "TEMP", "tmp",
    "Cache", "cache", ".cache",
    "Thumbnails",
    ".Spotlight-V100",
    ".Trashes",
}

# --- Image extensions ---
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".heic", ".heif", ".raw", ".cr2", ".nef", ".arw",
    ".ico", ".svg",
}

# --- Document / media for "other files" grouping ---
DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".rtf"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}


def is_junk(path: Path, base: Path) -> bool:
    """True if path is considered junk (file or dir)."""
    name = path.name
    if path.is_file():
        if name in JUNK_NAMES:
            return True
        suf = path.suffix.lower()
        if suf in JUNK_EXTENSIONS:
            return True
        if name.endswith("~"):
            return True
    else:
        if name in JUNK_FOLDER_NAMES:
            return True
    return False


def scan_junk(root: Path, report: list[dict]) -> None:
    """Append junk items to report (path, size, reason)."""
    try:
        for entry in root.rglob("*"):
            try:
                if not entry.exists():
                    continue
                if entry.is_file():
                    if is_junk(entry, root):
                        try:
                            size = entry.stat().st_size
                        except OSError:
                            size = 0
                        report.append({"path": str(entry), "size": size, "reason": "junk_file"})
                elif entry.is_dir() and is_junk(entry, root):
                    report.append({"path": str(entry), "size": 0, "reason": "junk_dir"})
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass


def file_hash(path: Path, block: int = 65536) -> str:
    """SHA256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_duplicates(root: Path, report: list[dict], min_size: int = 1) -> None:
    """Find duplicate files by size then hash; append groups to report."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    try:
        for entry in root.rglob("*"):
            try:
                if entry.is_file() and not is_junk(entry, root):
                    size = entry.stat().st_size
                    if size >= min_size:
                        by_size[size].append(entry)
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass

    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for p in paths:
            try:
                h = file_hash(p)
                by_hash[h].append(p)
            except (PermissionError, OSError):
                continue
        for h, group in by_hash.items():
            if len(group) >= 2:
                report.append({
                    "size": size,
                    "paths": [str(p) for p in sorted(group)],
                    "count": len(group),
                })


def scan_images(root: Path, report: list[dict]) -> None:
    """List all image files for sorting suggestion."""
    try:
        for entry in root.rglob("*"):
            try:
                if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
                    try:
                        mtime = entry.stat().st_mtime
                        report.append({
                            "path": str(entry),
                            "ext": entry.suffix.lower(),
                            "mtime": mtime,
                            "date": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"),
                        })
                    except OSError:
                        report.append({"path": str(entry), "ext": entry.suffix.lower(), "mtime": 0, "date": ""})
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass


def scan_other_files(root: Path, report: list[dict], limit: int = 500) -> None:
    """List non-image, non-junk files by extension for organization suggestion."""
    by_ext: dict[str, list[str]] = defaultdict(list)
    count = 0
    try:
        for entry in root.rglob("*"):
            if count >= limit:
                break
            try:
                if entry.is_file() and not is_junk(entry, root):
                    ext = entry.suffix.lower() or "(no ext)"
                    if ext not in IMAGE_EXTENSIONS:
                        by_ext[ext].append(str(entry))
                        count += 1
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    report.append({"by_extension": {k: v for k, v in by_ext.items()}, "total_sampled": count})


def main() -> None:
    ap = argparse.ArgumentParser(description="Organize E: drive – junk, duplicates, images, files")
    ap.add_argument("--drive", default="E:\\", help="Drive or root path to scan (default: E:\\)")
    ap.add_argument("--report-junk", action="store_true", default=True, help="Report junk files/dirs (default: on)")
    ap.add_argument("--no-report-junk", action="store_false", dest="report_junk")
    ap.add_argument("--report-dupes", action="store_true", default=True, help="Report duplicate files (default: on)")
    ap.add_argument("--no-report-dupes", action="store_false", dest="report_dupes")
    ap.add_argument("--report-images", action="store_true", default=True, help="Report images for sorting (default: on)")
    ap.add_argument("--no-report-images", action="store_false", dest="report_images")
    ap.add_argument("--report-files", action="store_true", default=True, help="Report other files by type (default: on)")
    ap.add_argument("--no-report-files", action="store_false", dest="report_files")
    ap.add_argument("--execute", action="store_true", help="Actually delete junk and move/organize (use with care)")
    ap.add_argument("--organize-images", action="store_true", help="Move images into Images/YYYY/MM (only with --execute)")
    ap.add_argument("--organize-files", action="store_true", help="Move docs/video/audio into subfolders (only with --execute)")
    args = ap.parse_args()

    root = Path(args.drive).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Path does not exist or is not a directory: {root}")
        return

    print(f"Scanning: {root}")
    print("=" * 60)

    # --- Junk ---
    if args.report_junk:
        junk_report: list[dict] = []
        scan_junk(root, junk_report)
        total_junk_size = sum(r["size"] for r in junk_report if r["reason"] == "junk_file")
        print(f"\n[JUNK] Found {len(junk_report)} items ({total_junk_size / (1024*1024):.2f} MB in files)")
        for r in junk_report[:100]:
            print(f"  {r['path']}")
        if len(junk_report) > 100:
            print(f"  ... and {len(junk_report) - 100} more")
        if args.execute and junk_report:
            for r in junk_report:
                p = Path(r["path"])
                try:
                    if p.is_file():
                        p.unlink()
                        print(f"  Deleted (junk): {p}")
                    elif p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                        print(f"  Removed (junk dir): {p}")
                except Exception as e:
                    print(f"  Skip {p}: {e}")

    # --- Duplicates ---
    if args.report_dupes:
        dup_report: list[dict] = []
        scan_duplicates(root, dup_report)
        total_dup_waste = sum((r["count"] - 1) * r["size"] for r in dup_report)
        print(f"\n[DUPLICATES] Found {len(dup_report)} duplicate groups ({total_dup_waste / (1024*1024):.2f} MB reclaimable)")
        for r in dup_report[:20]:
            print(f"  Size {r['size']} B, {r['count']} copies:")
            for p in r["paths"][:3]:
                print(f"    {p}")
            if len(r["paths"]) > 3:
                print(f"    ... and {len(r['paths'])-3} more")
        if len(dup_report) > 20:
            print(f"  ... and {len(dup_report) - 20} more groups")
        if args.execute and dup_report:
            for r in dup_report:
                # Keep first path (alphabetically), delete the rest
                keep, remove = r["paths"][0], r["paths"][1:]
                for p in remove:
                    try:
                        Path(p).unlink()
                        print(f"  Deleted (duplicate): {p}")
                    except Exception as e:
                        print(f"  Skip {p}: {e}")

    # --- Images ---
    if args.report_images:
        img_report: list[dict] = []
        scan_images(root, img_report)
        by_date = defaultdict(list)
        for r in img_report:
            by_date[r.get("date", "")].append(r["path"])
        print(f"\n[IMAGES] Found {len(img_report)} image files")
        for date in sorted(by_date.keys(), reverse=True)[:10]:
            print(f"  {date}: {len(by_date[date])} files")
        if args.execute and args.organize_images and img_report:
            images_base = root / "Images"
            for r in img_report:
                src = Path(r["path"])
                if not src.exists():
                    continue
                date = r.get("date", "unknown")
                if len(date) >= 7:
                    y, m = date[:4], date[5:7]
                    dest_dir = images_base / y / m
                else:
                    dest_dir = images_base / "unknown"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src.name
                if dest == src:
                    continue
                if dest.exists():
                    base, ext = src.stem, src.suffix
                    n = 1
                    while dest.exists():
                        dest = dest_dir / f"{base}_{n}{ext}"
                        n += 1
                try:
                    shutil.move(str(src), str(dest))
                    print(f"  Moved: {src} -> {dest}")
                except Exception as e:
                    print(f"  Skip {src}: {e}")

    # --- Other files ---
    if args.report_files:
        files_report: list[dict] = []
        scan_other_files(root, files_report)
        if files_report:
            be = files_report[0].get("by_extension", {})
            print(f"\n[OTHER FILES] Sampled {files_report[0].get('total_sampled', 0)} files by extension")
            for ext in sorted(be.keys(), key=lambda x: -len(be[x]))[:15]:
                print(f"  {ext}: {len(be[ext])} files")
        if args.execute and args.organize_files and files_report:
            be = files_report[0].get("by_extension", {})
            for ext, paths in be.items():
                if ext in DOC_EXTENSIONS:
                    folder = "Documents"
                elif ext in VIDEO_EXTENSIONS:
                    folder = "Videos"
                elif ext in AUDIO_EXTENSIONS:
                    folder = "Audio"
                else:
                    folder = "Other"
                dest_base = root / folder
                dest_base.mkdir(parents=True, exist_ok=True)
                for path in paths:
                    src = Path(path)
                    if not src.exists():
                        continue
                    dest = dest_base / src.name
                    if dest == src:
                        continue
                    if dest.exists():
                        base, suf = src.stem, src.suffix
                        n = 1
                        while dest.exists():
                            dest = dest_base / f"{base}_{n}{suf}"
                            n += 1
                    try:
                        shutil.move(str(src), str(dest))
                        print(f"  Moved: {src} -> {dest}")
                    except Exception as e:
                        print(f"  Skip {src}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
