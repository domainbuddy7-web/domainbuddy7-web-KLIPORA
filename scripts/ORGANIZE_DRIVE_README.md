# E: Drive Organizer

Script: `organize_drive.py`

## What it does

1. **Junk** – Finds and can remove:
   - `Thumbs.db`, `desktop.ini`, `.DS_Store`
   - `*.tmp`, `*.temp`, `*.bak`, `*.old`, `*.log`, `*.cache`, `.crdownload`, etc.
   - Folders: `Temp`, `Cache`, `__MACOSX`, `.Trash`, etc.

2. **Duplicates** – Finds files with identical content (by hash). Reports groups; with `--execute` keeps one copy and deletes the rest.

3. **Images** – Lists all image files. With `--execute --organize-images`, moves them into:
   - `E:\Images\YYYY\MM\` (by date modified).

4. **Other files** – Samples files by extension. With `--execute --organize-files`, moves:
   - Documents (pdf, doc, xls, etc.) → `E:\Documents\`
   - Videos → `E:\Videos\`
   - Audio → `E:\Audio\`
   - Rest → `E:\Other\`

## Usage

**Report only (safe, no changes):**
```powershell
cd E:\KLIPORA\scripts
python organize_drive.py --drive E:\
```

**Clean junk only:**
```powershell
python organize_drive.py --drive E:\ --execute
```

**Also organize images and other files:**
```powershell
python organize_drive.py --drive E:\ --execute --organize-images --organize-files
```

**Only duplicates report (no junk):**
```powershell
python organize_drive.py --drive E:\ --no-report-junk --report-dupes
```

**Different drive/path:**
```powershell
python organize_drive.py --drive D:\
```

## Notes

- First run **without** `--execute` to review the report.
- Duplicate deletion keeps the first path alphabetically and removes the others.
- Image/file moves may create `Images`, `Documents`, `Videos`, `Audio`, `Other` at the drive root.
- Full E: scan can take a while; use a subfolder to test: `--drive E:\TestFolder`.
