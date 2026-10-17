#!/usr/bin/env python3
"""Refuse a Nexus upload unless the exact playtested QA artifact was approved."""
import argparse
import hashlib
import json
import re
from pathlib import Path

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--version",required=True)
    a.add_argument("--run-id",required=True,type=int)
    a.add_argument("--archive",required=True,type=Path)
    args=a.parse_args()
    root=Path(__file__).resolve().parent.parent
    review=json.loads((root/"korean"/"release-approval.json").read_text(encoding="utf8"))
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._-]{0,48}",args.version):
        raise ValueError("Unsafe version string")
    if review.get("approved") is not True: raise ValueError("Linguistic/gameplay QA not approved")
    if review.get("version")!=args.version: raise ValueError("Approval version mismatch")
    if review.get("candidate_run_id")!=args.run_id: raise ValueError("Candidate Actions run mismatch")
    if review.get("linguistic_review") is not True: raise ValueError("Linguistic review not completed")
    if not review.get("reviewer"): raise ValueError("Reviewer identity missing")
    checks=review.get("playtest",{})
    for key in ("menu","dialogue","save_load","combat","restore"):
        if checks.get(key) is not True: raise ValueError("Playtest missing: "+key)
    if not args.archive.is_file(): raise ValueError("Approved archive missing")
    observed=hashlib.sha256(args.archive.read_bytes()).hexdigest()
    if observed!=review.get("package_sha256"): raise ValueError("Approved ZIP SHA-256 mismatch")
    print("RELEASE_APPROVED",args.version,observed,args.run_id)
if __name__=="__main__":main()
