#!/usr/bin/env python3
"""Compare contextual translations with identical 12-line blind baseline suite.

Inputs contain English, verified SSL roles and character profiles but NEVER
give model the gold Korean or pre-existing Korean during generation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from benchmark_translation_specialists import cases
from contextual_review_queue import (
    ROOT, MODEL_HY, MODEL_GEMMA, profiles, source_paths,
    record_for, contextual_translation, compare, glossary_for, enforce_terms,
)


def run(max_cases: int, out: Path):
    config = profiles()
    english_paths, script_paths = source_paths()
    out.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {
        "protocol": "blind gold; same 12 cases; English + exact same-HEAD SSL roles",
        "results": {},
    }
    for source in list(cases())[:max_cases]:
        speaker = source["file"].split("-")[0]
        msg = source["id"]
        key = f"{speaker}#{msg}"
        if key in data["results"] and all(
                model in data["results"][key].get("translations", {})
                for model in [MODEL_HY, MODEL_GEMMA]):
            continue
        item = record_for(
            ROOT / "data" / "text" / "korean" / "dialog" / (speaker + ".msg"),
            msg, english_paths, script_paths, config)
        # Guard benchmark integrity: previous bad/gold text is never sent.
        assert item["english"].strip() == source["english"].strip()
        row = {
            "file": speaker, "msg_id": msg,
            "english": source["english"], "original_bad": source["before"],
            "gold_korean": source["gold"],
            "ssl_role": item["evidence"]["roles"],
            "ssl_nodes": item["evidence"]["nodes"],
            "translations": {},
        }
        for model in [MODEL_HY, MODEL_GEMMA]:
            start = time.monotonic()
            value = contextual_translation(
                model, item["english"], item["context"], timeout=180)
            row["translations"][model] = {
                "korean": value,
                "seconds": round(time.monotonic() - start, 2),
                "flags": compare(source["gold"], value, source["english"])
                + enforce_terms(
                    value, glossary_for(source["english"], config), config),
            }
            print(speaker, msg, model, value[:180], flush=True)
        data["results"][key] = row
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-cases", type=int, default=12)
    ap.add_argument("--out", type=Path, default=ROOT /
                    "korean-contextual-review" / "benchmark12.json")
    args = ap.parse_args()
    run(args.max_cases, args.out)
