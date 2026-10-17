#!/usr/bin/env python3
"""Read-only git tree comparison against a pinned Korean release baseline."""
import argparse
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import subprocess

MSG = re.compile(rb"\{\s*(\d+)\s*\}\{([^{}]*)\}\{([^{}]*)\}", re.S)
TEXT = re.compile(r"(?:^|/)text/english/(.+)$", re.I)
RELEVANT = {".ssl", ".h", ".int", ".ini", ".cfg", ".json", ".lst", ".xml", ".bat", ".sh"}

def git(repo, *args, raw=False):
    result=subprocess.run(["git","-C",str(repo),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:raise RuntimeError(result.stderr.decode("utf8","replace"))
    return result.stdout if raw else result.stdout.decode("utf8","replace").strip()

def entries(blob):
    out={}
    for m in MSG.finditer(blob):
        key=str(int(m.group(1)))
        out[key]=(m.group(2).strip(),m.group(3).replace(b"\r\n",b"\n").strip())
    return out

def compare_msg(old,new,korean=None):
    a,b=entries(old),entries(new)
    t=entries(korean) if korean is not None else {}
    changed=[]
    for key in sorted(a.keys()|b.keys(),key=int):
        kind=("added" if key not in a else "removed" if key not in b else "modified" if a[key]!=b[key] else None)
        if kind:
            changed.append({"id":key,"kind":kind,"has_korean_id":key in t,
                            "requires_translation":kind!="removed","requires_review":True})
    return changed

def matching_korean(path,source_files):
    match=TEXT.search(path)
    if not match:return None,[]
    ending="/text/korean/"+match.group(1).lower()
    candidates=[row for row in source_files if row["path"].lower().endswith(ending)]
    direct=[row for row in candidates if "/data/text/korean/" in row["path"].lower() or row["path"].lower().startswith("data/text/korean/")]
    if len(direct)==1:return direct[0],candidates
    if len(candidates)==1:return candidates[0],candidates
    return None,candidates

def make_report(repo,base,head):
    meta=json.loads((repo/"korean/manifest.json").read_text(encoding="utf8"))
    baseline=git(repo,"rev-parse",base)
    current=git(repo,"rev-parse",head)
    changed=[]
    for ln in git(repo,"diff","--no-renames","--name-status",baseline,current).splitlines():
        parts=ln.split("\t")
        if len(parts)>=2:changed.append({"status":parts[0],"path":parts[1]})
    english=[row for row in changed if row["path"].lower().endswith(".msg") and TEXT.search(row["path"])]
    related=[row for row in changed if row not in english and
            (Path(row["path"]).suffix.lower() in RELEVANT or "/text/english/" in row["path"].lower())]
    msg_rows=[]
    ids=Counter()
    for row in english[:400]:
        path,status=row["path"],row["status"]
        old=git(repo,"show",baseline+":"+path,raw=True) if status!="A" else b""
        new=git(repo,"show",current+":"+path,raw=True) if status!="D" else b""
        matched,candidates=matching_korean(path,meta["files"])
        korean=None
        if matched:
            korean=repo.joinpath(*Path(matched["path"]).parts).read_bytes()
            if hashlib.sha256(korean).hexdigest()!=matched["sha256"]:
                raise ValueError("Translation hash mismatch: "+matched["path"])
        modifications=compare_msg(old,new,korean)
        ids.update(x["kind"] for x in modifications)
        msg_rows.append({"source":path,"status":status,"translated":matched["path"] if matched else None,
                         "matching_candidates":len(candidates),"changes":modifications})
    return {"schema":1,"baseline_name":meta["baseline"],"baseline_sha":baseline,
            "upstream_repo":meta["upstream"],"upstream_sha":current,
            "changed_files":len(changed),"changed_english_msg":len(english),
            "analyzed_msg":len(msg_rows),"analysis_truncated":len(english)>400,
            "changed_id_counts":dict(ids),"msg_files":msg_rows,"related_files":related,
            "other_file_count":len(changed)-len(english)-len(related)}

def as_markdown(r):
    lines=["# Korean translation upstream review","",
           "Source: "+r["upstream_repo"],
           "Pinned translation baseline: "+r["baseline_name"]+" ("+r["baseline_sha"][:12]+")",
           "Current upstream master: "+r["upstream_sha"][:12],
           "Files changed: "+str(r["changed_files"]),
           "English MSG files: "+str(r["changed_english_msg"]),
           "MSG IDs: "+json.dumps(r["changed_id_counts"]),
           "Script/config changes: "+str(len(r["related_files"])),"",
           "No code auto-merge or machine translation is performed.","",
           "## English MSG changes",""]
    if r["analysis_truncated"]:lines+=["CAUTION: analysis truncated after 400 MSG files.", ""]
    for row in r["msg_files"][:80]:
        lines.append("- "+row["status"]+" "+row["source"]+" -> "+(row["translated"] or "UNMAPPED")+"; changed IDs "+str(len(row["changes"])))
        for it in row["changes"][:4]:
            lines.append("  - "+it["id"]+": "+it["kind"]+", translation "+("present" if it["has_korean_id"] else "missing"))
    if len(r["msg_files"])>80:lines.append("Remaining MSG files are in report.json.")
    lines+=["","## Script / config / non-MSG text changes",""]
    for row in r["related_files"][:80]:lines.append("- "+row["status"]+" "+row["path"])
    if len(r["related_files"])>80:lines.append("Remaining paths are in report.json.")
    lines+=["","## Review procedure","",
            "1. Reconcile newly added or changed English MSG IDs and related scripts manually.",
            "2. Update Korean translation and pinned manifest after review.",
            "3. Build translation-only ZIP, validate in a test copy, never overwrite a production install automatically.",
            "4. No Korean renderer/game EXE bundled; Text Engine is maintained separately.",""]
    return "\n".join(lines)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--repo",type=Path,default=Path(__file__).resolve().parent.parent)
    a.add_argument("--head",default="FETCH_HEAD")
    a.add_argument("--report-dir",type=Path,default=Path("korean-report"))
    args=a.parse_args()
    repo=args.repo.resolve()
    conf=json.loads((repo/"korean/watch-config.json").read_text(encoding="utf8"))
    report=make_report(repo,conf["baseline_sha"],args.head)
    dest=args.report_dir.resolve()
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    (dest/"report.md").write_text(as_markdown(report),encoding="utf8")
    print("UPSTREAM_REVIEW",report["baseline_name"],"changed",report["changed_files"],
          "english_msg",report["changed_english_msg"],"IDs",report["changed_id_counts"],flush=True)

if __name__=="__main__":main()
