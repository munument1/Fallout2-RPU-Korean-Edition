#!/usr/bin/env python3
"""Build a review-only Windows setup ZIP containing the thin installer."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import os
import subprocess
import sys
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

def sha(path):
    return sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--skip-compile",action="store_true")
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    cfg_file=root/"korean-dist"/"installer-config.json"
    zip_file=root/"korean-dist"/"korean-translation-only.zip"
    if not cfg_file.is_file() or not zip_file.is_file():
        raise SystemExit("Run build_overlay.py and build_combined.py first.")
    config=json.loads(cfg_file.read_text(encoding="utf8"))
    name={"ettu":"Fallout-Et-Tu-Korean-Setup","rpu":"Fallout2-RPU-Korean-Setup"}[config["game"]]
    dest=root/"korean-candidate-dist"
    dest.mkdir(exist_ok=True)
    exe=dest/(name+".exe")
    if not args.skip_compile:
        if os.name!="nt":
            raise SystemExit("Standalone Windows EXE must be compiled on Windows.")
        cmd=[sys.executable,"-m","PyInstaller","--noconfirm","--clean","--onefile",
             "--windowed","--noupx","--log-level=WARN","--name",name,
             "--distpath",str(dest),"--workpath",str(root/"korean-dist"/"pyinstaller"),
             "--specpath",str(root/"korean-dist"),
             "--add-data",str(cfg_file)+os.pathsep+"data",
             "--add-data",str(zip_file)+os.pathsep+"data",
             str(root/"korean"/"combined_installer.py")]
        subprocess.run(cmd,cwd=root,check=True)
    if not exe.is_file():raise SystemExit("EXE packaging failed")
    subprocess.run([str(exe),"--verify-bundle"],check=True)
    candidate={
        "qa_status":"NOT_APPROVED",
        "game":config["game"],"version_baseline":config["game_baseline"],
        "translation_sha256":config["zip_sha256"],
        "engine_version":config["engine_version"],
        "engine_sha256":config["engine_sha256"],
        "installer_exe_sha256":sha(exe),
        "warning":"Game installs, gameplay, speech review and full release QA are pending.",
    }
    (dest/"CANDIDATE_INFO.json").write_text(json.dumps(candidate,indent=2)+"\n",encoding="utf8")
    readme=("KOREAN INSTALLER QA CANDIDATE - NOT A STABLE RELEASE\n\n"
            "This ZIP embeds translation data in a setup helper. The common renderer\n"
            "is fetched from the central Text Engine beta release during installation\n"
            "and its SHA-256 is verified before it runs. No game EXE is distributed.\n"
            "1. Work on a COPY of a legitimately installed game.\n"
            "2. Run the setup EXE. Select the game/mod root directory.\n"
            "3. The shared engine setup opens; select the SAME root and install.\n"
            "4. Test menu, NPC dialogue, combat, save/load. The installer keeps\n"
            "   a separate translation data backup for recovery.\n"
            "5. For engine recovery, reopen the central Text Engine setup.\n"
            "WARNING: Korean text register review and long-play testing NOT complete.\n")
    bundle=dest/(name+".zip")
    with ZipFile(bundle,"w",compression=ZIP_DEFLATED,compresslevel=8) as archive:
        for filename,blob in [
            (name+".exe",exe.read_bytes()),
            ("CANDIDATE_INFO.json",(dest/"CANDIDATE_INFO.json").read_bytes()),
            ("READ_ME_FIRST.txt",readme.encode("utf8")),
        ]:
            info=ZipInfo(filename,date_time=(1980,1,1,0,0,0))
            info.compress_type=ZIP_DEFLATED
            archive.writestr(info,blob)
    (dest/"SHA256SUMS.txt").write_text(
        sha(bundle)+"  "+bundle.name+"\n"+sha(exe)+"  "+exe.name+"\n",encoding="ascii")
    print(json.dumps({"candidate_zip":str(bundle),"sha256":sha(bundle),
                      "installer_sha256":sha(exe),"qa_approved":False}))
if __name__=="__main__":
    main()
