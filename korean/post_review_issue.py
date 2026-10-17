#!/usr/bin/env python3
"""Upsert one actionable review issue (no duplicates per upstream SHA)."""
from pathlib import Path
from urllib.request import Request, urlopen
import json
import os

TITLE="[Korean translation] Upstream changes need review"

def call(method,url,token,data=None):
    payload=json.dumps(data).encode("utf8") if data is not None else None
    req=Request(url,data=payload,method=method,headers={
        "Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28","User-Agent":"korean-translation-watch",
        "Content-Type":"application/json"})
    with urlopen(req,timeout=45) as f:return json.load(f)

r=json.loads(Path("korean-report/report.json").read_text(encoding="utf8"))
if r["changed_files"]==0:
    print("Upstream baseline matches; no issue")
    raise SystemExit(0)
repo=os.environ["GITHUB_REPOSITORY"]
token=os.environ["GH_TOKEN"]
base="https://api.github.com/repos/"+repo
issues=call("GET",base+"/issues?state=open&per_page=100",token)
existing=next((i for i in issues if i.get("title")==TITLE and "pull_request" not in i),None)
marker="<!-- SHA:"+r["upstream_sha"]+" -->"
if existing and marker in (existing.get("body") or ""):
    print("Review issue already up to date:",existing["number"])
    raise SystemExit(0)
run_url="https://github.com/"+repo+"/actions/runs/"+os.environ["GITHUB_RUN_ID"]
body=marker+"\n"+Path("korean-report/report.md").read_text(encoding="utf8")[:45000]+"\nFull JSON: "+run_url+"\n"
if existing:
    call("PATCH",base+"/issues/"+str(existing["number"]),token,{"body":body})
    print("Updated review issue:",existing["number"])
else:
    created=call("POST",base+"/issues",token,{"title":TITLE,"body":body})
    print("Created review issue:",created["number"])
