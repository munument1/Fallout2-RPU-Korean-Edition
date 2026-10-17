#!/usr/bin/env python3
"""Evaluate local translation-first models against previously audited RPU dialogue.

No game/MSG data is ever modified by this script. Gold translations were created
independently of the tested models and may have legitimate alternative phrasings.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CASES = [
    ("qhprzrch-followup-v2.4.34-20261017.csv", 250),
    ("qhprzrch-followup-v2.4.34-20261017.csv", 266),
    ("qhprzrch-followup-v2.4.34-20261017.csv", 276),
    ("ahmonk-v2.4.34-20261017.csv", 900),
    ("kcsulik-register-semantics-v2.4.34-20261017.csv", 711),
    ("kcsulik-register-semantics-v2.4.34-20261017.csv", 731),
    ("ocgoris-v2.4.34-20261017.csv", 144),
    ("ahelder-semantics-v2.4.34-20261017.csv", 150),
    ("kcsulik-register-semantics-v2.4.34-20261017.csv", 251),
    ("vclynett-followup-20261017.csv", 441),
    ("qhprzrch-finalpass-v2.4.34-20261017.csv", 218),
    ("ahelder-semantics-v2.4.34-20261017.csv", 137),
]


def cases():
    for path, mid in CASES:
        with (ROOT / "korean" / "reviews" / path).open(
                newline="", encoding="utf-8-sig") as f:
            selected = next(
                (x for x in csv.DictReader(f) if int(x["msg_id"]) == mid),
                None,
            )
        if selected is None:
            raise ValueError(f"Missing gold record: {path} ID {mid}")
        yield {
            "file": path, "id": mid, "role": selected["speaker_context"],
            "english": selected["english"].replace("\r\n", " ").strip(),
            "before": selected["previous_korean"].replace("\r\n", " ").strip(),
            "gold": selected["updated_korean"].replace("\r\n", " ").strip(),
        }


def historical_100_cases():
    """Stratified frozen selection across all eight already-reviewed speakers."""
    if str(ROOT / "korean") not in sys.path:
        sys.path.insert(0, str(ROOT / "korean"))
    from auto_review_queue import parse_msg

    per_speaker = {
        "qhprzrch": 25, "vclynett": 16, "kcsulik": 16,
        "hcmarcus": 14, "ahmonk": 10, "acwarior": 8,
        "ahelder": 6, "ocgoris": 5,
    }
    gold_per_speaker: dict[str, dict[int, dict]] = {}
    review_dir = ROOT / "korean" / "reviews"
    for speaker in per_speaker:
        # Only records explicitly corrected in existing Korean/English/SSL QA.
        available: dict[int, dict] = {}
        for path in sorted(review_dir.glob(speaker + "-*.csv")):
            with path.open("r", newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                if not {"msg_id", "english", "previous_korean", "updated_korean"} <= row.keys():
                    continue
                try:
                    mid = int(row["msg_id"])
                except (TypeError, ValueError):
                    continue
                english = row["english"].replace("\r\n", " ").strip()
                if not (16 <= len(english) <= 550):
                    continue
                if not re.search("[A-Za-z]", english):
                    continue
                if "%s" in english or "%d" in english:
                    continue
                available.setdefault(mid, {
                    "file": path.name, "id": mid,
                    "role": row.get("speaker_context", ""),
                    "english": english,
                    "before": row["previous_korean"].replace("\r\n", " ").strip(),
                })
        current, warnings = parse_msg(
            (ROOT / "data" / "text" / "korean" / "dialog" /
             (speaker + ".msg")).read_bytes()
        )
        allowed = {}
        for mid, row in available.items():
            if mid not in current or not current[mid]["text"]:
                continue
            row["gold"] = current[mid]["text"].replace("\r\n", " ").strip()
            allowed[mid] = row
        if len(allowed) < per_speaker[speaker]:
            raise ValueError(
                f"Need {per_speaker[speaker]} benchmark examples "
                f"for {speaker}, found {len(allowed)}"
            )
        # Choose across the sorted ID span instead of taking just opening lines.
        ids = sorted(allowed)
        desired = per_speaker[speaker]
        selected = [ids[round(i * (len(ids) - 1) / (desired - 1))]
                    for i in range(desired)]
        gold_per_speaker[speaker] = {i: allowed[i] for i in selected}
    for speaker, items in gold_per_speaker.items():
        for row in items.values():
            yield row


def prompt(model: str, english: str) -> str:
    if model.startswith("translategemma"):
        return (
            "You are a professional English (en) to Korean (ko) translator. "
            "Your goal is to accurately convey the meaning and nuances of "
            "the original English text while adhering to Korean grammar, "
            "vocabulary, and cultural sensitivities.\n"
            "Produce only the Korean translation, without any additional "
            "explanations or commentary. Please translate the following "
            "English text into Korean:\n\n\n" + english
        )
    # Tencent Hy-MT2 official direct translation prompt, deliberately without
    # a character glossary for the first apples-to-apples baseline.
    return (
        "Translate the following text into Korean. Note that you should "
        "only output the translated result without any additional explanation:\n"
        + english
    )


def translate(model: str, english: str, timeout: int):
    opts = {"num_ctx": 4096, "num_predict": 500, "temperature": 0.2}
    if "Hy-MT2" in model:
        opts.update({"temperature": 0.7, "top_p": 0.6, "top_k": 20,
                     "repeat_penalty": 1.05})
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt(model, english)}],
        "stream": False,
        "think": False,
        "options": opts,
        "keep_alive": "2m",
    }
    req = Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as f:
        result = json.load(f)
    return result["message"]["content"].strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "korean-auto-review" /
                    "translation-specialists.json")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--suite", choices=["focused12", "gold100"],
                    default="focused12")
    ap.add_argument("--timeout", type=int, default=150)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.out.read_text("utf-8")) if args.out.exists() else {
        "protocol": "translation-first; original English alone; no SSL/context hints",
        "benchmarks": {},
    }
    existing = data["benchmarks"].setdefault(args.model, {})
    suite = historical_100_cases() if args.suite == "gold100" else cases()
    for sample in list(suite)[:args.limit]:
        key = f"{sample['file']}#{sample['id']}"
        if key in existing and not existing[key].get("error"):
            continue
        started = time.monotonic()
        result = dict(sample)
        try:
            result["translation"] = translate(
                args.model, sample["english"], args.timeout)
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {str(exc)[:260]}"
        result["elapsed_sec"] = round(time.monotonic() - started, 2)
        existing[key] = result
        args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        print(f"[{args.model}] {sample['id']} {sample['file']} "
              f"({result['elapsed_sec']}s) => "
              f"{result.get('translation',result.get('error'))[:200]}",
              flush=True)


if __name__ == "__main__":
    main()
