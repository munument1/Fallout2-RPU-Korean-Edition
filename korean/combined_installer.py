#!/usr/bin/env python3
"""Offline translation overlay + verified, centrally hosted Korean engine.

The single Windows setup EXE embeds only Korean translation data, never a
proprietary game EXE or a copy of the common engine. It fetches the pinned
engine from the canonical GitHub release when needed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from zipfile import ZipFile

ENGINE_BACKUP="korean_engine_backup_v2"
TEXT_BACKUP="korean_translation_backup_v1"
STATE_FILE="state.json"
ALLOWED_SUFFIXES={".msg",".bio",".txt",".ini",".lst"}
MAX_ZIP_BYTES=80*1024*1024
MAX_ITEM_BYTES=3*1024*1024


def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def config_bundle(config_path=None,zip_path=None):
    base=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent.parent))
    config_path=Path(config_path) if config_path else base/"data"/"installer-config.json"
    zip_path=Path(zip_path) if zip_path else base/"data"/"korean-translation-only.zip"
    cfg=json.loads(config_path.read_text(encoding="utf-8-sig"))
    if cfg.get("schema")!=1 or cfg.get("game") not in ("ettu","rpu"):
        raise ValueError("Unrecognized installer configuration.")
    if len(cfg["zip_sha256"])!=64 or digest(zip_path.read_bytes())!=cfg["zip_sha256"]:
        raise ValueError("Translation ZIP SHA-256 check failed.")
    members={}
    with ZipFile(zip_path) as z:
        files=[i for i in z.infolist() if not i.is_dir()]
        if len(files)!=cfg["file_count"] or sum(i.file_size for i in files)>MAX_ZIP_BYTES:
            raise ValueError("Translation ZIP content count/size mismatch.")
        for info in files:
            path=PurePosixPath(info.filename)
            if (path.is_absolute() or not path.parts or ".." in path.parts
                or "." in path.parts or ":" in info.filename
                or "\\" in info.filename or path.suffix.lower() not in ALLOWED_SUFFIXES
                or info.file_size>MAX_ITEM_BYTES or len(info.filename)>260):
                raise ValueError("Unsafe translation ZIP member: "+info.filename)
            folded=info.filename.lower()
            if folded in members:
                raise ValueError("Windows-insensitive filename collision: "+info.filename)
            members[folded]=(info.filename,z.read(info))
    return cfg,members

def checked_target(raw:Path,game:str)->Path:
    if not raw.is_dir() or raw.is_symlink():
        raise ValueError("Choose a valid game copy folder, not a link.")
    root=raw.resolve(strict=True)
    fold=str(root).lower().replace("/","\\")
    if ("\\steamapps\\common\\" in fold or "\\program files" in fold):
        raise ValueError("Install on a separate copy, not Steam/Program Files.")
    names={p.name.lower() for p in root.iterdir() if p.is_file()}
    if not (names & {"fallout2.exe","fallout2","fores.exe","fallout2hr.exe"}):
        raise ValueError("Game executable was not detected in the chosen folder.")
    if not (root/"data").is_dir():
        raise ValueError("Game data folder not detected.")
    if game=="ettu":
        if (root/"Fallout1in2").is_dir() and not (root/"mods").is_dir():
            raise ValueError("Select the Fallout1in2 folder, not its parent.")
        markers=[root/"mods"/"fo1_base",root/"mods"/"fo1_base.dat",root/"data"/"text"/"english"]
        if not any(x.exists() for x in markers) and "ettu" not in root.name.lower() and "fallout1in2" not in root.name.lower() and "et-tu" not in root.name.lower() and "fo1in2" not in root.name.lower():
            raise ValueError("Et Tu mod markers not found; refusing a possible RPU folder.")
    if game=="rpu" and (root/"mods"/"fo1_base").exists():
        raise ValueError("Et Tu detected, but this installer targets RPU.")
    return root

def checked_path(root:Path,rel:str)->Path:
    candidate=root.joinpath(*PurePosixPath(rel).parts)
    current=root
    for component in PurePosixPath(rel).parts:
        current=current/component
        if current.is_symlink():
            raise ValueError("Refusing a symlink in translation destination: "+rel)
    # Windows may present the same folder with different path casing or 8.3
    # aliases. Python Path.is_relative_to is lexical/case-sensitive even on NT.
    # Normalize BOTH sides and require a component-boundary common parent.
    normalized_root=os.path.normcase(os.path.abspath(str(root.resolve(strict=True))))
    normalized_target=os.path.normcase(os.path.abspath(str(candidate.resolve(strict=False))))
    if os.path.commonpath((normalized_root,normalized_target))!=normalized_root:
        raise ValueError("Target path escapes the game folder.")
    return candidate

def verified_engine(root:Path)->bool:
    backup=root/ENGINE_BACKUP
    state=backup/"manifest.json"
    if not state.is_file() or state.is_symlink():
        return False
    try:
        data=json.loads(state.read_text(encoding="utf8"))
        after=data["after"]
        if not isinstance(after,dict) or not after:
            return False
        for rel,expected in after.items():
            path=checked_path(root,rel)
            if not path.is_file() or digest(path.read_bytes())!=expected:
                return False
        return True
    except (ValueError,KeyError,OSError,TypeError):
        return False

def install_translations(root:Path,members:dict,cfg:dict):
    backup=root/TEXT_BACKUP
    if backup.exists():
        raise ValueError("Translation backup already exists. Restore first; never overwrite it.")
    # Preflight all source bytes/destinations before making any changes.
    for _,(name,blob) in members.items():
        checked_path(root,name)
        if len(blob)>MAX_ITEM_BYTES:
            raise ValueError("Invalid translation size")
    backup.mkdir()
    old={}
    written=[]
    try:
        for key,(rel,data) in members.items():
            target=checked_path(root,rel)
            old[key]={"path":rel,"before":digest(target.read_bytes()) if target.is_file() else None,
                      "after":digest(data)}
            if target.is_file():
                snapshot=backup/"original"/Path(*PurePosixPath(rel).parts)
                snapshot.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(target,snapshot)
        (backup/STATE_FILE).write_text(json.dumps({
            "schema":1,"game":cfg["game"],"source_zip_sha256":cfg["zip_sha256"],
            "files":list(old.values())},indent=2),encoding="utf8")
        for key,(rel,blob) in members.items():
            target=checked_path(root,rel)
            target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+".korean-install-tmp")
            if temp.exists():raise ValueError("Existing staging file: "+str(temp))
            try:
                temp.write_bytes(blob)
                os.replace(temp,target)
            finally:
                if temp.exists():temp.unlink()
            written.append(rel)
        return len(written)
    except BaseException:
        # The state records all candidate files and restores only installed bytes.
        restore_translations(root,strict=False)
        raise

def restore_translations(root:Path,strict=True):
    backup=root/TEXT_BACKUP
    if not backup.is_dir() or not (backup/STATE_FILE).is_file():
        raise ValueError("No translation backup to restore.")
    state=json.loads((backup/STATE_FILE).read_text(encoding="utf8"))
    items=state["files"]
    # Strictly reject user edits before touching any files.
    if strict:
        for item in items:
            target=checked_path(root,item["path"])
            if target.is_file() and digest(target.read_bytes()) not in (item["after"],item["before"]):
                raise ValueError("User-edited file; refuse overwrite: "+item["path"])
    restored=0
    for item in reversed(items):
        target=checked_path(root,item["path"])
        if target.is_file() and digest(target.read_bytes())!=item["after"]:
            continue
        if item["before"] is None:
            if target.exists():target.unlink()
        else:
            original=backup/"original"/Path(*PurePosixPath(item["path"]).parts)
            if not original.is_file() or digest(original.read_bytes())!=item["before"]:
                if strict:raise ValueError("Backup mismatch: "+item["path"])
                continue
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original,target)
        restored+=1
    if strict:
        shutil.rmtree(backup)
    return restored

def download_engine(cfg,output:Path):
    url=cfg["engine_url"]
    if not url.startswith("https://github.com/munument1/Fallout2-Korean-Text-Engine/releases/download/"):
        raise ValueError("Unexpected engine download host/path")
    with urllib.request.urlopen(url,timeout=90) as stream,output.open("wb") as f:
        shutil.copyfileobj(stream,f)
    if digest(output.read_bytes())!=cfg["engine_sha256"]:
        output.unlink(missing_ok=True)
        raise ValueError("Engine executable hash mismatch - abort.")
    return output

def install(root:Path,cfg:dict,members:dict):
    root=checked_target(root,cfg["game"])
    already=verified_engine(root)
    count=install_translations(root,members,cfg)
    if not already:
        try:
            with tempfile.TemporaryDirectory(prefix="fallout-korean-engine-") as temporary:
                engine_exe=download_engine(cfg,Path(temporary)/"Fallout2-Korean-Native-Setup.exe")
                subprocess.run([str(engine_exe)],check=False)
            if not verified_engine(root):
                raise ValueError("Engine patch not verified; translation overlay will be rolled back. "
                                 "Choose the SAME game folder in the engine window and complete installation.")
        except BaseException:
            restore_translations(root,strict=True)
            raise
    return count,already

def dialog():
    import tkinter as tk
    from tkinter import filedialog,messagebox
    root=tk.Tk()
    root.title("Fallout Korean integrated beta installer")
    root.geometry("615x205")
    location=tk.StringVar()
    tk.Label(root,text="Select a COPY of your Fallout game folder. "
             "This setup will run the verified shared Text Engine if needed.",wraplength=570).pack(pady=8)
    holder=tk.Frame(root);holder.pack(fill="x",padx=12)
    tk.Entry(holder,textvariable=location,width=70).pack(side="left",expand=True,fill="x")
    tk.Button(holder,text="Browse",command=lambda:location.set(filedialog.askdirectory())).pack(side="right")
    def go(restore=False):
        try:
            cfg,members=config_bundle()
            target=checked_target(Path(location.get()),cfg["game"])
            if not messagebox.askyesno("Confirm",
                ("RESTORE translation data? " if restore else "INSTALL Korean data and engine? ")
                +"Target: "+str(target)+"\nOnly use a COPY of the game."):
                return
            if restore:
                n=restore_translations(target)
                messagebox.showinfo("Restored",f"Restored {n} translation files. Engine restore is separate.")
            else:
                n,already=install(target,cfg,members)
                messagebox.showinfo("Done",f"Applied {n} translation files; engine verified. "
                                     +"Please test menus, save/load, dialogue and combat.")
        except Exception as exc:
            messagebox.showerror("Installation stopped",str(exc))
    row=tk.Frame(root);row.pack(pady=20)
    tk.Button(row,text="Install (beta)",command=go,width=25).pack(side="left",padx=10)
    tk.Button(row,text="Restore translations",command=lambda:go(True),width=25).pack(side="left",padx=10)
    root.mainloop()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--verify-bundle",action="store_true")
    p.add_argument("--config-file",type=Path)
    p.add_argument("--zip-file",type=Path)
    p.add_argument("--install-dir",type=Path)
    p.add_argument("--restore-dir",type=Path)
    args=p.parse_args()
    if args.verify_bundle:
        cfg,members=config_bundle(args.config_file,args.zip_file)
        print(json.dumps({"game":cfg["game"],"translation_files":len(members),
                          "engine_version":cfg["engine_version"]}))
        return 0
    if args.install_dir or args.restore_dir:
        cfg,members=config_bundle(args.config_file,args.zip_file)
        target=checked_target(args.install_dir or args.restore_dir,cfg["game"])
        if args.restore_dir:
            print("Restored:",restore_translations(target))
        else:
            print("Installed:",install(target,cfg,members))
        return 0
    dialog()
    return 0

if __name__=="__main__":
    sys.exit(main())
