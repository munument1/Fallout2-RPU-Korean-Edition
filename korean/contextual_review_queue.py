#!/usr/bin/env python3
"""NPC-aware Fallout RPU bilingual comparison, with persistent resumable results.

Pure candidate generation: game files, translations, Git state and release
manifests are never changed. Requires Ollama locally when not in --status mode.
Model results are not error-free and MUST NOT be automatically approved.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from auto_review_queue import ROOT, git, parse_msg, ordered_files, source_paths

SCRIPT_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
SCRIPT_LINE_COMMENT = re.compile(r"//[^\r\n]*")
SCRIPT_PROC = re.compile(r"\bprocedure\s+(\w+)\s+begin\b", re.I)
NPC_REPLY = re.compile(r"\bReply\s*\(\s*(\d+)\s*\)", re.I)
OPTION = re.compile(r"\b(?:NOption|BOption|GOption|NLowOption|giq_option|gsay_option)"
                    r"\s*\(\s*(\d+)\s*,", re.I)
FRAGMENT = re.compile(r"\bmstr\s*\(\s*(\d+)\s*\)", re.I)
PROFILE_PATH = ROOT / "korean" / "contextual_review_profiles.json"
OUT = ROOT / "korean-contextual-review"
MODEL_HY = "hf.co/tencent/Hy-MT2-7B-GGUF:Q8_0"
MODEL_GEMMA = "translategemma:12b"


def profiles():
    data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    assert data["baseline"] == "RPU 2.4.34"
    return data


def current_script_text(path: str) -> str:
    """Read only matching HEAD SSL; never mix newer upstream branches."""
    raw = git("show", "HEAD:" + path, binary=True)
    # Preserve newlines and alignment while excluding comments.
    s = raw.decode("latin-1")
    s = SCRIPT_BLOCK_COMMENT.sub(
        lambda m: re.sub(r"[^\r\n]", " ", m.group()), s)
    s = SCRIPT_LINE_COMMENT.sub(
        lambda m: " " * len(m.group()), s)
    return s


def ssl_evidence(script: str, ids: set[int]) -> dict[int, dict]:
    """Exact role by Reply/Option + associated SSL node and code evidence."""
    lines = script.splitlines()
    proc = "unknown"
    by_id: dict[int, dict] = {
        i: {"roles": [], "nodes": [], "lines": []} for i in ids
    }
    # Declarations can be separate from procedure bodies, only a "begin"
    # identifies a real block. A reference in a comment has been erased.
    for index, line in enumerate(lines, 1):
        match = SCRIPT_PROC.search(line)
        if match:
            proc = match[1]
        reply = {int(x) for x in NPC_REPLY.findall(line)}
        opts = {int(x) for x in OPTION.findall(line)}
        fragments = {int(x) for x in FRAGMENT.findall(line)}
        # A source statement like Reply(mstr(120) + " " + mstr(122))
        # is still an NPC Reply, even though the literal IDs are inside mstr.
        # Do not generalize to display_msg(mstr(...)) or floating text.
        if re.search(r"\bReply\s*\(", line, re.I):
            reply |= fragments
        for mid in (reply | opts | fragments) & ids:
            row = by_id[mid]
            if mid in reply and "npc_reply" not in row["roles"]:
                row["roles"].append("npc_reply")
            if mid in opts and "player_option" not in row["roles"]:
                row["roles"].append("player_option")
            if mid in fragments and "string_fragment" not in row["roles"]:
                row["roles"].append("string_fragment")
            if proc not in row["nodes"]:
                row["nodes"].append(proc)
            if len(row["lines"]) < 3:
                # Give the model one true source line, not neighboring comments.
                row["lines"].append(f"{index}: {line.strip()[:160]}")
    for row in by_id.values():
        if not row["roles"]:
            row["roles"] = ["unmapped"]
        row["nodes"] = row["nodes"][:3]
    return by_id


def speaker_profile(stem: str, role: list[str], cfg: dict) -> dict:
    """Never transfer NPC speech formality to a player's choices."""
    known = cfg["speakers"].get(stem.lower())
    if "player_option" in role and "npc_reply" in role:
        return {"speaker": "AMBIGUOUS ROLE - PC/NPC conflict",
                "register": "분기 확인 전 화자 말투를 고정하지 말 것",
                "extra": "Both NPC and player roles detected."}
    if "player_option" in role:
        return {"speaker": "PLAYER character", "register":
                "플레이어 선택지다. NPC 말투 지정 금지. 원문의 선택지 분위기를 따를 것",
                "extra": "Could be insulting, low intelligence, formal or sarcastic."}
    if "npc_reply" in role and known:
        return known
    return {"speaker": "NOT CONFIRMED", "register":
            "화자·상황 확인 전 존댓말/반말 임의 통일 금지. 원문과 기존 한국어 어조 비교",
            "extra": "The MSG file can contain multiple NPCs, PC options and narration."}


def glossary_for(src: str, cfg: dict) -> dict:
    terms = cfg["general_glossary"]
    def matches(word: str):
        # English source often pluralizes named nouns ("vertibirds").
        suffix = "s?" if word.isalpha() and not word.lower().endswith("s") else ""
        return re.search(
            r"(?<!\w)" + re.escape(word) + suffix + r"(?!\w)", src, re.I)
    return {k: v for k, v in terms.items() if matches(k)}


def context_background(stem: str, mid: int, english: str,
                       reference: dict, cfg: dict, nearby: list[dict]) -> str:
    persona = speaker_profile(stem, reference["roles"], cfg)
    g = glossary_for(english, cfg)
    info = {
        "game": "Fallout 2 Restoration Project Updated v2.4.34",
        "filename": stem + ".msg", "message_id": mid,
        "speaker": persona["speaker"], "korean_register": persona["register"],
        "character_notes": persona["extra"],
        "script_role": reference["roles"],
        "ssl_procedures": reference["nodes"],
        "ssl_source_lines": reference["lines"],
        "required_terms": g,
        "adjoining_ids_not_guaranteed_same_branch": nearby[:4],
    }
    return json.dumps(info, ensure_ascii=False)


def contextual_translation(model: str, english: str, background: str,
                           timeout: int = 160) -> str:
    from urllib.request import Request, urlopen
    if model == MODEL_HY:
        query = (
            "[Background Information]\n" + background +
            "\n[Source Text]\n" + english +
            "\nTranslate the [Source Text] into Korean. Use the background "
            "only to choose the speaker's tone and correct game terminology. "
            "Output ONLY the translated Korean text, without explanation. "
            "Preserve the meaning of hostile language and sarcasm."
        )
        opts = {"temperature": 0.7, "top_p": 0.6, "top_k": 20,
                "repeat_penalty": 1.05}
    else:
        query = (
            "You are a professional English-to-Korean translator. "
            "Context for terminology, character and dialogue branch:\n" +
            background +
            "\nTranslate the following English text into Korean using this "
            "context. Preserve intent, speaking register, game proper nouns, "
            "and stylistic features. Respond ONLY with the translation.\n" +
            english
        )
        opts = {"temperature": 0.2}
    opts.update({"num_predict": 750, "num_ctx": 8192})
    body = {"model": model, "messages": [{"role": "user", "content": query}],
            "stream": False, "think": False, "keep_alive": "2m",
            "options": opts}
    req = Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as res:
        return json.load(res)["message"]["content"].strip()


def compare(base: str, variant: str, english: str) -> list[str]:
    """Only machine-verifiable red flags, not semantic error approval."""
    from auto_review_queue import PERCENT
    flags = []
    if not variant:
        flags.append("empty_output")
    try:
        variant.encode("cp949")
    except UnicodeError:
        flags.append("not_cp949")
    if PERCENT.findall(base) != PERCENT.findall(variant):
        flags.append("placeholder_mismatch")
    for name, regex in (("markup", re.compile(r"<[^>]*>")),
                        ("linebreak", re.compile(r"\r\n|\r|\n"))):
        if regex.findall(base) != regex.findall(variant):
            flags.append(name + "_changed")
    if re.fullmatch(r"[\x00-\x7f]+", variant) and re.search("[가-힣]", base):
        flags.append("probably_untranslated")
    # Existing records may contain game engine syntax, which must never
    # disappear merely because a second model rewrites the sentence.
    if re.findall(r"\[\w+\]", base) != re.findall(r"\[\w+\]", variant):
        flags.append("bracketed_directives_changed")
    return flags


def enforce_terms(translation: str, found_terms: dict, cfg: dict):
    """Flag only strict glossary anchors; never make an automatic edit."""
    failures = []
    hard = set(cfg["required_game_terms"])
    for term, korean in found_terms.items():
        if term not in hard:
            continue
        if korean.casefold() not in translation.casefold():
            failures.append(f"glossary_violation:{term}->{korean}")
    return failures


def record_for(path: Path, mid: int, english_map: dict, script_map: dict,
               cfg: dict, *, src_english: dict | None = None,
               src_korean: dict | None = None, source_ssl: str | None = None):
    stem = path.stem.lower()
    ko = src_korean
    if ko is None:
        ko, _ = parse_msg(path.read_bytes())
    en = src_english
    if en is None:
        en_path = english_map.get("data/text/english/dialog/" + path.name.lower())
        if not en_path:
            raise ValueError(f"No baseline English: {path.name}")
        en, _ = parse_msg(git("show", "HEAD:" + en_path, binary=True))
    if mid not in en or mid not in ko:
        raise ValueError(f"Missing English/KO ID {mid} in {path.name}")
    scripts = script_map.get(stem, [])
    ssl_path = scripts[0] if len(scripts) == 1 else None
    s = source_ssl
    if s is None and ssl_path:
        s = current_script_text(ssl_path)
    evidence = ssl_evidence(s or "", {mid})[mid]
    other_ids = sorted(set(ko) & set(en))
    pivot = other_ids.index(mid)
    neighbors = [
        {"id": i, "english": en[i]["text"][:170]}
        for i in other_ids[max(0, pivot - 2):pivot + 3] if i != mid
    ]
    current = ko[mid]["text"]
    assert isinstance(current, str) and isinstance(en[mid]["text"], str)
    return {
        "msg_id": mid, "file": path.relative_to(ROOT).as_posix(),
        "english": en[mid]["text"], "korean_current": current,
        "voice_id": ko[mid]["voice"], "script_path": ssl_path,
        "evidence": evidence,
        "context": context_background(
            stem, mid, en[mid]["text"], evidence, cfg, neighbors),
    }


def result_key(item: dict, models: list[str]) -> str:
    values = [item["file"], str(item["msg_id"]),
              item["english"], item["korean_current"],
              item["context"], ",".join(models)]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode(
        "utf-8")).hexdigest()[:24]


def save_json_atomic(path: Path, value: dict):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    os.replace(temp, path)


def evaluate_one(item: dict, models: list[str], timeout: int,
                 cfg: dict | None = None) -> dict:
    comparison = {}
    active_terms = glossary_for(item["english"], cfg) if cfg else {}
    for model in models:
        start = time.monotonic()
        translation = contextual_translation(
            model, item["english"], item["context"], timeout)
        comparison[model] = {
            "translation": translation,
            "time_seconds": round(time.monotonic() - start, 2),
            "structural_flags": compare(
                item["korean_current"], translation, item["english"])
                + (enforce_terms(translation, active_terms, cfg) if cfg else []),
        }
    first = comparison[models[0]]["translation"]
    second = comparison[models[-1]]["translation"]
    from difflib import SequenceMatcher
    disagreement = 1 - SequenceMatcher(
        None, first, second).ratio() if len(models) > 1 else None
    return {**item, "models": comparison, "model_disagreement": disagreement,
            "status": "requires_contextual_human_QA",
            "automatically_approved": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="Optional single MSG stem, e.g. ocgoris")
    ap.add_argument("--ids", help="Optional comma separated numeric MSG IDs")
    ap.add_argument("--model", choices=["hy", "both"], default="both")
    ap.add_argument("--max-items", type=int, default=5)
    ap.add_argument("--max-minutes", type=float, default=15)
    ap.add_argument("--timeout", type=int, default=150)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
        "completed": {}, "errors": {}, "model_mode": args.model,
    }
    if args.status:
        print(json.dumps({
            "completed": len(state["completed"]),
            "errors": len(state.get("errors", {})), "model_mode": state["model_mode"],
            "out": str(out),
        }, ensure_ascii=False))
        return
    if state["model_mode"] != args.model:
        ap.error("Different model configuration requires a new --out directory")
    models = [MODEL_HY] if args.model == "hy" else [MODEL_HY, MODEL_GEMMA]
    cfg = profiles()
    english_map, script_map = source_paths()
    paths = ordered_files()
    if args.file:
        stem = Path(args.file).stem.lower()
        paths = [p for p in paths if p.stem.lower() == stem]
        if len(paths) != 1:
            ap.error("No unique file found: " + stem)
    selected_ids = None
    if args.ids:
        try:
            selected_ids = {int(x.strip()) for x in args.ids.split(",")}
        except ValueError:
            ap.error("--ids must be comma separated integers")
        if not args.file:
            ap.error("--ids requires --file to prevent selecting other NPCs")
    deadline = time.monotonic() + 60 * args.max_minutes
    done = 0
    for path in paths:
        en_path = english_map.get("data/text/english/dialog/" + path.name.lower())
        if not en_path:
            continue
        english, en_warnings = parse_msg(git("show", "HEAD:" + en_path, binary=True))
        korean, ko_warnings = parse_msg(path.read_bytes())
        paths_ssl = script_map.get(path.stem.lower(), [])
        ssl = current_script_text(paths_ssl[0]) if len(paths_ssl) == 1 else ""
        for mid in sorted(set(english) & set(korean)):
            if selected_ids is not None and mid not in selected_ids:
                continue
            if time.monotonic() >= deadline or done >= args.max_items:
                print(f"PAUSED {done} this run; total "
                      f"{len(state['completed'])}", flush=True)
                return
            if f"ambiguous_record:{mid}" in en_warnings + ko_warnings:
                continue
            item = record_for(
                path, mid, english_map, script_map, cfg,
                src_english=english, src_korean=korean, source_ssl=ssl)
            key = result_key(item, models)
            if key in state["completed"]:
                continue
            try:
                result = evaluate_one(item, models, args.timeout, cfg=cfg)
                result["key"] = key
                # Report first; checkpoint only after append succeeds.
                with (out / "comparisons.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    f.flush()
                state["completed"][key] = {"file": item["file"], "id": mid}
                save_json_atomic(state_path, state)
                done += 1
                print(f"NEW {item['file']} ID {mid} "
                      f"flagged={sum(bool(v['structural_flags']) for v in result['models'].values())} "
                      f"total={len(state['completed'])}", flush=True)
            except Exception as ex:
                state["errors"][key] = f"{type(ex).__name__}: {str(ex)[:160]}"
                save_json_atomic(state_path, state)
                print(f"ERROR {path.name} {mid}: {ex}", file=sys.stderr, flush=True)
                raise SystemExit(2)
    print("COMPLETE", len(state["completed"]))


if __name__ == "__main__":
    main()
