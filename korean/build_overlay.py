#!/usr/bin/env python3
"""Export a verified Korean translation overlay without upstream binaries."""
from pathlib import Path
import hashlib
import json
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
meta = json.loads((root / "korean" / "manifest.json").read_text(encoding="utf8"))
output = root / "korean-dist" / "korean-translation-only.zip"
output.parent.mkdir(exist_ok=True)
with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=8) as archive:
    for item in meta["files"]:
        file = root.joinpath(*Path(item["path"]).parts)
        data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise SystemExit("Translation SHA-256 mismatch: " + item["path"])
        archive.writestr(item["zip_path"], data)
with ZipFile(output) as archive:
    if len(archive.namelist()) != len(meta["files"]):
        raise SystemExit("Missing output files")
print("Translation ZIP built:", output, len(meta["files"]))
