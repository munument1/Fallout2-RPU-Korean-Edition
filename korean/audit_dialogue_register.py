#!/usr/bin/env python3
"""Conservative Fallout Korean dialogue register audit.

Read-only: generated reports are review leads, never automatic translation edits.
NPC replies are identified via script Reply(<literal ID>) or voice tags. Other lines
are excluded, because a dialogue MSG mixes player options and narrator text.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import subprocess

LINE_RE = re.compile(rb"\{\s*(\d+)\s*\}\{([^{}]*)\}\{([^{}]*)\}", re.S)
NPC_RE = re.compile(rb"\bReply\s*\(\s*(\d+)\s*\)", re.I)
PLAYER_RE = re.compile(rb"\b(?:NOption|GOption|BOption|giq_option|gsay_option)\s*\(\s*(\d+)\s*[,)]", re.I)
# Sentence-end style is evidence, not a judgement. Only the final clause is classified.
FORMAL = re.compile(r"(?:습니다|습니까|십시오|으십시오|니다|십니까)$")
HAO = re.compile(r"(?:하오|겠소|하시오|마시오|하소|구려|거요|소|오)$")
POLITE = re.compile(r"(?:세요|으세요|이에요|예요|해요|돼요|어요|아요|네요|군요|지요|죠|까요|나요|요)$")
PLAIN = re.compile(r"(?:했어|겠어|했지|하지|거야|잖아|거든|해|돼|줘|야|어|아|지|네|군|냐|니|다|라|자|게)$")
SKIP_PREFIX = ("#", "//")
HEADERS = ["game","speaker_file","id","voice_id","source_role","certainty",
           "style","text","file_path","script_path"]
MAX_LINES=500

def git(repo,*args,raw=False):
    res=subprocess.run(["git","-C",str(repo),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if res.returncode:
        raise RuntimeError("git "+repr(args)+": "+res.stderr.decode("utf8","replace")[:250])
    return res.stdout if raw else res.stdout.decode("utf8","replace").splitlines()

def classify(txt):
    text=txt.strip()
    punctuation={" ",".","!","?","(",")","[","]",chr(34),chr(39),
                 chr(0x3002),chr(0xff01),chr(0xff1f),chr(0x2026)}
    while text and (text[-1] in punctuation or text[-1].isspace()):
        text=text[:-1]
    if not text:return "undetermined"
    tail=re.split(r"[.!?\u3002\uff01\uff1f\u2026\n]",text)[-1].strip()
    if not tail:return "undetermined"
    if tail in {"\uB124","\uC608","\uC751","\uC544\uB2C8","\uC544\uB2C8\uC694","\uC74C","\uD760"}:
        return "undetermined"
    if FORMAL.search(tail):return "formal"
    if HAO.search(tail):return "hao"
    if POLITE.search(tail):return "polite"
    if PLAIN.search(tail):return "plain"
    return "undetermined"

def msg_rows(data):
    for m in LINE_RE.finditer(data):
        msgid=int(m.group(1))
        voice=m.group(2).decode("latin-1").strip()
        text=m.group(3).decode("cp949","replace").strip()
        if text and not text.startswith(SKIP_PREFIX):
            yield msgid,voice,text

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--out",type=Path,default=Path("korean-speech-report"))
    parser.add_argument("--script-limit",type=int,default=0,
                        help="Max mapped scripts to inspect. Default zero: all scripts with matching dialogue file")
    args=parser.parse_args()
    repo=args.repo.resolve()
    meta=json.loads((repo/"korean/manifest.json").read_text(encoding="utf-8"))
    entries=[row for row in meta["files"] if "/text/korean/dialog/" in row["path"].lower()
             and row["path"].lower().endswith(".msg")]
    script_paths=git(repo,"ls-tree","-r","--name-only","HEAD")
    source_dirs=("scripts_src/","Mapper/source/scripts/")
    mapping=defaultdict(list)
    for path in script_paths:
        if path.lower().endswith(".ssl") and any(part.lower() in path.lower() for part in source_dirs):
            mapping[Path(path).stem.lower()].append(path)
    groups=defaultdict(list)
    samples=[]
    coverage=Counter()
    loaded_scripts=0
    for entry in entries:
        path=Path(entry["path"])
        dialogue_stem=path.stem.lower()
        options=mapping.get(dialogue_stem,[])
        matched=options[0] if len(options)==1 else None
        npc_ids=set()
        player_ids=set()
        if matched and (args.script_limit==0 or loaded_scripts<args.script_limit):
            try:
                script=git(repo,"show","HEAD:"+matched,raw=True)
                npc_ids={int(x) for x in NPC_RE.findall(script)}
                player_ids={int(x) for x in PLAYER_RE.findall(script)}
                loaded_scripts+=1
            except (RuntimeError, ValueError):
                coverage["script_read_errors"]+=1
        else:
            if len(options)>1:coverage["ambiguous_scripts"]+=1
        raw=repo.joinpath(*path.parts).read_bytes()
        if __import__("hashlib").sha256(raw).hexdigest()!=entry["sha256"]:
            raise ValueError("Source translation changed, update manifest first: "+str(path))
        coverage["files_checked"]+=1
        all_rows=list(msg_rows(raw))
        for msgid,voice,txt in all_rows:
            coverage["dialogue_lines"]+=1
            if msgid in player_ids and msgid in npc_ids:
                coverage["script_role_conflicts"]+=1
                continue
            if msgid in player_ids:
                coverage["excluded_player_options"]+=1
                continue
            if msgid in npc_ids:
                why="script_reply"
                certainty="high"
            elif voice:
                why="voice_id"
                certainty="medium" if not matched else "high"
            else:
                coverage["unattributed_lines"]+=1
                continue
            style=classify(txt)
            if style=="undetermined":
                coverage["unclassified_npc_lines"]+=1
                continue
            coverage["classified_npc_lines"]+=1
            row={"game":meta["baseline"],"speaker_file":path.stem,"id":msgid,
                 "voice_id":voice,"source_role":why,"certainty":certainty,
                 "style":style,"text":txt[:350],"file_path":str(path),
                 "script_path":matched or ""}
            groups[str(path)].append(row)
        if len(samples)<4 and len(groups[str(path)])>10:
            samples.append(path.stem)
    findings=[]
    for path,lines in groups.items():
        per=Counter(row["style"] for row in lines)
        if len(per)<2 or sum(per.values())<3:continue
        strong=[kind for kind in ("formal","polite","hao","plain") if per[kind]]
        if len(strong)<2:continue
        # Distinct adjacent styles are not automatically errors, just review candidates.
        findings.append({
            "speaker_file":Path(path).stem,
            "file_path":path,
            "style_counts":dict(per),
            "samples":{kind:[{"id":r["id"],"text":r["text"][:220],"evidence":r["source_role"]}
                              for r in lines if r["style"]==kind][:4] for kind in strong},
            "flags":["register_mixing_candidate","check_situational_context",
                     "check_if_multiple_npcs_share_dialogue_file"],
            "review_needed":True
        })
    findings.sort(key=lambda x:(len(x["style_counts"]),sum(x["style_counts"].values())),reverse=True)
    out=args.out.resolve()
    out.mkdir(exist_ok=True,parents=True)
    report={"generated_utc":datetime.now(timezone.utc).isoformat(),"game":meta["baseline"],
            "coverage":dict(coverage),"scripts_read":loaded_scripts,
            "mixed_register_candidates":len(findings),"findings":findings,
            "limitation":"File stems approximate speakers; voice tags or literal Reply() IDs only. "
                         "Context switches and NPC role ambiguity require human validation. "
                         "No automatic edits or release approval."}
    (out/"register-review.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    with (out/"speaker-lines.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=HEADERS)
        writer.writeheader()
        for lines in groups.values():
            for row in lines:writer.writerow(row)
    summary=[f"# {meta['baseline']} 말투 일관성 검수 초안",
             "",f"- 검수 대상 MSG 파일: {coverage['files_checked']:,}개",
             f"- 전체 대사 항목: {coverage['dialogue_lines']:,}개",
             f"- NPC 후보 말투 판정: {coverage['classified_npc_lines']:,}개",
             f"- 말투 혼용 검수 후보 파일: **{len(findings):,}개**",
             "- 이 보고서는 오류 확정이 아닙니다. 플레이어 선택지·상황에 따른 말투 전환·다인 대화 가능성을 반드시 확인하세요.",
             ""]
    for finding in findings[:60]:
        summary+=["## "+finding["speaker_file"],"",
                  "분포: "+str(finding["style_counts"])]
        for kind, rows in finding["samples"].items():
            for item in rows[:2]:
                summary.append(f"- [{kind}] ID {item['id']}: {item['text'][:130]}")
        summary.append("")
    if len(findings)>60:
        summary.append(f"나머지 {len(findings)-60}개는 JSON에서 확인하세요.")
    (out/"register-review.md").write_text("\n".join(summary)+"\n",encoding="utf8")
    print(json.dumps({"game":meta["baseline"],"coverage":dict(coverage),
          "script_files":loaded_scripts,"mixed_files":len(findings),"path":str(out)},ensure_ascii=False))
if __name__=="__main__":
    main()
