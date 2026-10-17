#!/usr/bin/env python3
"""Update ONLY specified byte-verified Korean manifest entries after human review."""
from pathlib import Path
import argparse
import hashlib
import json

def main():
    a=argparse.ArgumentParser()
    a.add_argument("paths",nargs="+",help="Exact repository-relative source paths of reviewed translations")
    a.add_argument("--apply",action="store_true",
                   help="Explicitly accept these reviewed source changes into the manifest")
    opts=a.parse_args()
    root=Path(__file__).resolve().parent.parent
    path=root/"korean"/"manifest.json"
    meta=json.loads(path.read_text(encoding="utf8"))
    index={row["path"].replace("\\","/"):row for row in meta["files"]}
    edits=[]
    for rel in opts.paths:
        target=index.get(rel.replace("\\","/"))
        if target is None:
            raise ValueError("Not a known Korean translation source: "+rel)
        p=root.joinpath(*Path(target["path"]).parts)
        if not p.is_file() or p.is_symlink():
            raise ValueError("Missing or symlinked source: "+rel)
        blob=p.read_bytes()
        new=hashlib.sha256(blob).hexdigest()
        if new!=target["sha256"] or len(blob)!=target["bytes"]:
            edits.append((target,new,len(blob)))
    print("REVIEWED_FILE_CHANGES",len(edits))
    for row,sha,size in edits:
        print(row["path"],"sha256",row["sha256"],"=>",sha,"bytes",row["bytes"],"=>",size)
    if not opts.apply:
        print("Dry-run only. Add --apply after dialogue/text QA and byte-level review.")
        return
    if not edits:
        return
    for row,sha,size in edits:
        row["sha256"]=sha
        row["bytes"]=size
    path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("Updated manifest for",len(edits),"reviewed files; rerun build_overlay.py")
if __name__=="__main__":
    main()
