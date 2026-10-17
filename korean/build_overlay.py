#!/usr/bin/env python3
"""Export byte-exact, reproducible Korean ZIP from the approved manifest."""
from pathlib import Path
import hashlib
import json
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

root=Path(__file__).resolve().parent.parent
meta=json.loads((root/"korean"/"manifest.json").read_text(encoding="utf8"))
output=root/"korean-dist"/"korean-translation-only.zip"
output.parent.mkdir(exist_ok=True)
seen=set()
with ZipFile(output,"w",compression=ZIP_DEFLATED,compresslevel=8) as archive:
    for item in meta["files"]:
        relative=Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or item["zip_path"].lower() in seen:
            raise ValueError("Unsafe or duplicate manifest path.")
        seen.add(item["zip_path"].lower())
        data=root.joinpath(*relative.parts).read_bytes()
        if hashlib.sha256(data).hexdigest()!=item["sha256"]:
            raise SystemExit("Translation SHA-256 mismatch: "+item["path"])
        info=ZipInfo(item["zip_path"],date_time=(1980,1,1,0,0,0))
        info.compress_type=ZIP_DEFLATED
        info.external_attr=0o644<<16
        archive.writestr(info,data,compress_type=ZIP_DEFLATED,compresslevel=8)
with ZipFile(output) as z:
    if len(z.namelist())!=len(meta["files"]):
        raise SystemExit("ZIP manifest length mismatch")
print("REPRODUCIBLE_TRANSLATION_ZIP",output,len(meta["files"]),
      hashlib.sha256(output.read_bytes()).hexdigest())
