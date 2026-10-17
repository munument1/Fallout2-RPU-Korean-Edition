#!/usr/bin/env python3
"""Resumable, local-only Fallout 2 RPU translation review.

This creates inspectable candidate corrections, not modifications to game files.
The QA source of truth is the CP949 MSG + matching same-revision English and SSL.
Never write/commit/release unverified model output automatically.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEECH_REPORT = ROOT / "korean-full-speech-report" / "register-review.json"
DEFAULT_OUT = ROOT / "korean-auto-review"
HEADER = re.compile(r"(?m)^\{(\d+)\}\{([^}]+|)\}\{")
END = re.compile(r"\}(?:[ \t]*#[^\r\n]*)?(?:\r?\n[ \t]*(?:#[^\r\n]*)?)*\Z")
REPLY = re.compile(r"\bReply\s*\(\s*(\d+)\s*\)", re.I)
OPTION = re.compile(
    r"\b(?:NOption|GOption|BOption|NLowOption|giq_option|gsay_option)"
    r"\s*\(\s*(\d+)\s*[,)]", re.I
)
MSTR = re.compile(r"\bmstr\s*\(\s*(\d+)\s*\)", re.I)
PERCENT = re.compile(r"%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?[sdfox]")


def git(*args: str, binary: bool = False):
    proc = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True
    )
    if proc.returncode:
        raise RuntimeError(
            "git " + " ".join(args[:3]) + ": " +
            proc.stderr.decode("utf-8", "replace")[:200]
        )
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


def parse_msg(data: bytes) -> tuple[dict[int, dict], list[str]]:
    """Recover all record IDs, including Fallout MSG records with # comments."""
    text = data.decode("cp949")
    heads = list(HEADER.finditer(text))
    records: dict[int, dict] = {}
    warnings: list[str] = []
    for j, head in enumerate(heads):
        mid = int(head[1])
        if mid in records:
            warnings.append(f"duplicate_id:{mid}")
            continue
        end_pos = heads[j + 1].start() if j + 1 < len(heads) else len(text)
        tail = text[head.end():end_pos]
        closing = END.search(tail)
        if closing:
            content = tail[:closing.start()]
            # Keep line breaks inside dialogue, not the record separator.
        else:
            # Invalid/unusual payload: expose it for review, never auto-edit.
            warnings.append(f"ambiguous_record:{mid}")
            content = ""
        records[mid] = {"id": mid, "voice": head[2], "text": content}
    return records, warnings


def source_paths() -> tuple[set[str], dict[str, list[str]]]:
    names = git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
    english = {
        p.lower(): p for p in names
        if p.lower().startswith("data/text/english/dialog/") and p.lower().endswith(".msg")
    }
    scripts: dict[str, list[str]] = {}
    for p in names:
        if p.lower().endswith(".ssl") and p.lower().startswith("scripts_src/"):
            scripts.setdefault(Path(p).stem.lower(), []).append(p)
    return english, scripts


def script_context(path: str | None, selected: set[int]):
    if not path:
        return {}, []
    try:
        body = git("show", "HEAD:" + path, binary=True).decode("latin-1")
    except RuntimeError:
        return {}, ["script_read_error"]
    npc = {int(i) for i in REPLY.findall(body)}
    player = {int(i) for i in OPTION.findall(body)}
    # Dynamic mstr fragments may be part of the NPC's Reply. Do not
    # automatically treat them as a separate single-speaker certainty.
    fragments = {int(i) for i in MSTR.findall(body)}
    lines = body.splitlines()
    refs: dict[int, dict] = {}
    for mid in selected:
        kinds = set()
        if mid in npc:
            kinds.add("npc_reply")
        if mid in player:
            kinds.add("player_option")
        if not kinds and mid in fragments:
            kinds.add("mstr_fragment_or_conditional")
        if not kinds:
            kinds.add("unmapped")
        cites = []
        needle = re.compile(r"(?<!\d)" + str(mid) + r"(?!\d)")
        for line_no, line in enumerate(lines, 1):
            if needle.search(line) and any(
                tag in line for tag in ("Reply(", "Option(", "mstr(", "display_msg(")
            ):
                cites.append(f"{line_no}:{line.strip()[:140]}")
                if len(cites) >= 2:
                    break
        refs[mid] = {"roles": sorted(kinds), "ssl_lines": cites}
    return refs, []


def ordered_files() -> list[Path]:
    path = ROOT / "data" / "text" / "korean" / "dialog"
    files = sorted(path.glob("*.msg"), key=lambda x: x.name.casefold())
    # The eight previously reviewed NPC files are not complete, but put other
    # NPCs first so this automation finds NEW issues before rechecking them.
    earlier_reviewed = {
        "hcmarcus", "kcsulik", "vclynett", "qhprzrch",
        "acwarior", "ahmonk", "ahelder", "ocgoris",
    }
    if SPEECH_REPORT.exists():
        report = json.loads(SPEECH_REPORT.read_text(encoding="utf-8"))
        rankings = {
            row["speaker_file"].lower(): index
            for index, row in enumerate(report.get("findings", []))
        }
        files.sort(key=lambda f: (
            f.stem.lower() in earlier_reviewed,
            rankings.get(f.stem.lower(), 10_000), f.name
        ))
    else:
        files.sort(key=lambda f: (f.stem.lower() in earlier_reviewed, f.name))
    return files


def ollama_chat(model: str, prompt: str, timeout: int):
    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": (
                "You are a critical bilingual Korean localization QA reviewer. "
                "Correct meaning and grammar using exact English and SSL evidence; "
                "keep unique Fallout names and intentional tone shifts. "
                "NPC Reply and player Option are DIFFERENT speakers. "
                "Respond with a strict JSON object. Never invent English, context, or IDs."
            )},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0, "num_ctx": 12288, "num_predict": 1300},
        "keep_alive": "3m",
    }
    req = Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as res:
        result = json.load(res)
    raw = result.get("message", {}).get("content", "")
    answer = json.loads(raw)
    if not isinstance(answer, dict):
        raise ValueError("not a JSON object")
    return answer


def prompt_for(path: Path, lines: list[dict], refs: dict):
    compact = []
    for row in lines:
        mid = row["id"]
        compact.append({
            "id": mid,
            "voice": row["voice"],
            "English": row["english"][:1200],
            "Korean": row["korean"][:1200],
            "script": refs.get(mid, {"roles": ["unknown"], "ssl_lines": []}),
        })
    return (
        f"RPU v2.4.34 file {path.stem}. Every dialogue record below is a potential "
        "NPC reply, PLAYER choice, or system text. Check actual roles separately. "
        "Identify ONLY unmistakable mistranslations, untranslated text, factual "
        "reversals, broken particles, or unjustified politeness inconsistencies. "
        "If context is insufficient, do not recommend a correction. "
        "Return {\"suggestions\":[{\"id\":123,\"korean\":\"complete corrected Korean text\","
        "\"reason\":\"brief evidence from English/SSL\",\"confidence\":0.95}],"
        "\"uncertain_ids\":[123]}. Suggestions are NOT auto-applied. "
        "Don't include already correct text; do not change control sequences, "
        "format placeholders, or character identity. Do not claim the complete "
        "file was human-reviewed. The records are:\n"
        + json.dumps(compact, ensure_ascii=False)
    )


def safe_suggestions(answer: dict, rows: list[dict]):
    originals = {r["id"]: r for r in rows}
    allowed = []
    rejected = []
    seen = set()
    if not isinstance(answer.get("suggestions"), list):
        return [], ["missing_suggestions"]
    for item in answer["suggestions"]:
        try:
            mid = int(item["id"])
            text = item["korean"]
            confidence = float(item.get("confidence", 0))
            if not isinstance(text, str) or mid not in originals or mid in seen:
                raise ValueError("unknown ID, repeated ID, or non-text")
            seen.add(mid)
            current = originals[mid]["korean"]
            if text.strip() == current.strip() or not text.strip():
                raise ValueError("empty or no change")
            text.encode("cp949")
            if PERCENT.findall(text) != PERCENT.findall(current):
                raise ValueError("format placeholders changed")
            if text.count("<") != current.count("<") or text.count(">") != current.count(">"):
                raise ValueError("markup changed")
            if "\n" in text or "\r" in text:
                raise ValueError("model altered line layout")
            if len(text) > max(1400, len(current) * 3):
                raise ValueError("oversized replacement")
            allowed.append({
                "id": mid, "before": current, "proposal": text,
                "confidence": confidence, "reason": str(item.get("reason", ""))[:700],
                "status": "needs_independent_verification",
            })
        except (KeyError, TypeError, ValueError, UnicodeError) as ex:
            rejected.append(str(ex)[:140])
    return allowed, rejected


def save_state(path: Path, state: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_summary(path: Path, state: dict):
    done = len(state["completed_chunks"])
    files = len(state["files_seen"])
    lines = state["lines_reviewed"]
    path.write_text(
        "# Local Fallout 2 RPU review progress\n\n"
        f"- Chunks examined by local LLM: **{done:,}**\n"
        f"- Different files reached: **{files:,} / {state['total_files']:,}**\n"
        f"- Dialogue IDs examined: **{lines:,}** (may include revised-file reruns)\n"
        f"- Candidate corrections proposed: **{state['candidate_count']:,}**\n"
        f"- Failed batches (retry on next run): **{state['failed_batches']:,}**\n"
        f"- Last update: {datetime.now(timezone.utc).isoformat()}\n\n"
        "**Important:** Suggestions are unverified and NOT automatically "
        "written to CP949 game files or published. Source roles are inferred "
        "from exact SSL references; model omissions and wrong suggestions are possible.\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default="qwen3:14b")
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--max-minutes", type=float, default=120)
    parser.add_argument("--max-chunks", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.chunk_size <= 30:
        parser.error("chunk-size must be between 1 and 30")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
        "completed_chunks": [], "files_seen": [], "lines_reviewed": 0,
        "candidate_count": 0, "failed_batches": 0,
        "total_files": 0, "model": args.model,
    }
    if args.status:
        print(json.dumps({k: (len(v) if isinstance(v, list) else v)
                          for k, v in state.items()}, ensure_ascii=False))
        return
    if state.get("model") != args.model:
        parser.error("existing state uses a different model; choose a different --out")
    english_map, script_map = source_paths()
    files = ordered_files()
    state["total_files"] = len(files)
    completed = set(state["completed_chunks"])
    file_seen = set(state["files_seen"])
    deadline = time.monotonic() + 60 * args.max_minutes
    processed = 0
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        english_path = english_map.get("data/text/english/dialog/" + path.name.lower())
        if not english_path:
            # Never fabricate English source: missing source is a review concern.
            with (out / "missing_sources.txt").open("a", encoding="utf-8") as f:
                f.write(relative + "\n")
            continue
        try:
            korean, warnings = parse_msg(path.read_bytes())
            english, english_warnings = parse_msg(
                git("show", "HEAD:" + english_path, binary=True)
            )
        except (UnicodeError, RuntimeError) as ex:
            with (out / "source_errors.txt").open("a", encoding="utf-8") as f:
                f.write(relative + ": " + str(ex)[:200] + "\n")
            continue
        paths = script_map.get(path.stem.lower(), [])
        script_path = paths[0] if len(paths) == 1 else None
        if warnings or english_warnings or set(korean) != set(english):
            with (out / "structural_flags.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "file": relative, "KO_count": len(korean),
                    "EN_count": len(english),
                    "missing_KO": sorted(set(english) - set(korean)),
                    "extra_KO": sorted(set(korean) - set(english)),
                    "warnings": warnings + english_warnings,
                }, ensure_ascii=False) + "\n")
        ids = sorted(set(korean) & set(english))
        refs, _ = script_context(script_path, set(ids))
        raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        for offset in range(0, len(ids), args.chunk_size):
            subset = ids[offset:offset + args.chunk_size]
            label = f"{relative}|{raw_hash}|{args.model}|{','.join(map(str,subset))}"
            identifier = hashlib.sha256(label.encode("utf8")).hexdigest()[:24]
            if identifier in completed:
                continue
            if time.monotonic() >= deadline or (args.max_chunks and processed >= args.max_chunks):
                write_summary(out / "PROGRESS.md", state)
                return
            rows = [{
                "id": i, "voice": korean[i]["voice"],
                "korean": korean[i]["text"], "english": english[i]["text"],
            } for i in subset]
            try:
                answer = ollama_chat(args.model, prompt_for(path, rows, refs), args.timeout_seconds)
                proposals, rejected = safe_suggestions(answer, rows)
                result = {
                    "batch": identifier, "file": relative,
                    "script": script_path, "ids": subset,
                    "proposals": proposals, "rejected": rejected,
                    "uncertain_ids": answer.get("uncertain_ids", []),
                }
                with (out / "review-proposals.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                completed.add(identifier)
                state["completed_chunks"].append(identifier)
                file_seen.add(relative)
                state["files_seen"] = sorted(file_seen)
                state["lines_reviewed"] += len(rows)
                state["candidate_count"] += len(proposals)
                processed += 1
                save_state(state_path, state)
                print(f"reviewed {relative} IDs {subset[0]}..{subset[-1]}, "
                      f"proposals={len(proposals)}, batches={len(completed)}", flush=True)
            except (URLError, TimeoutError, ValueError, OSError, KeyError) as ex:
                state["failed_batches"] += 1
                save_state(state_path, state)
                print(f"retry next run: {relative} {subset[0]} "
                      f"{type(ex).__name__}: {str(ex)[:90]}", file=sys.stderr, flush=True)
                # If Ollama is off, avoid failing thousands of batches.
                if isinstance(ex, URLError):
                    write_summary(out / "PROGRESS.md", state)
                    raise SystemExit(2)
    write_summary(out / "PROGRESS.md", state)
    print(f"COMPLETE processed={len(completed)} proposals={state['candidate_count']}")


if __name__ == "__main__":
    main()
