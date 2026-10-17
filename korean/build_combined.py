#!/usr/bin/env python3
"""Generate a hash-pinned combined installer manifest for a release candidate."""
from pathlib import Path
import argparse
import hashlib
import json
from zipfile import ZipFile

ENGINE_URL=("https://github.com/munument1/Fallout2-Korean-Text-Engine/"
            "releases/download/v1.2.0-beta.2/Fallout2-Korean-Native-Setup.exe")
ENGINE_SHA="0223b962000683da6cb2dfe284f17f96036ffd102ce2cc0f053d41201fdbd1b7"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",type=Path,default=Path(__file__).resolve().parent.parent)
    args=parser.parse_args()
    root=args.repo.resolve()
    bundle=root/"korean-dist"/"korean-translation-only.zip"
    if not bundle.is_file():
        raise ValueError("Run python korean/build_overlay.py first.")
    src=json.loads((root/"korean"/"manifest.json").read_text(encoding="utf8"))
    game="ettu" if src["upstream"]=="rotators/Fo1in2" else (
         "rpu" if src["upstream"]=="BGforgeNet/Fallout2_Restoration_Project" else None)
    if not game:raise ValueError("Unexpected fork identity.")
    with ZipFile(bundle) as archive:
        names=[x.filename for x in archive.infolist() if not x.is_dir()]
    if len(names)!=len(src["files"]) or set(names)!={x["zip_path"] for x in src["files"]}:
        raise ValueError("Translation archive manifest mismatch.")
    result={
        "schema":1,"game":game,"game_baseline":src["baseline"],
        "zip_sha256":hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "file_count":len(names),"engine_url":ENGINE_URL,
        "engine_sha256":ENGINE_SHA,"engine_version":"v1.2.0-beta.2",
        "release_status":"candidate-needs-linguistic-and-gameplay-QA",
    }
    out=root/"korean-dist"/"installer-config.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result))
if __name__=="__main__":main()
