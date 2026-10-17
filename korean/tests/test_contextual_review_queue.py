import importlib.util
from pathlib import Path
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "rpu_contextual_review", ROOT / "contextual_review_queue.py"
)
import sys
sys.path.insert(0, str(ROOT))
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ContextualReviewTests(unittest.TestCase):
    def test_english_player_option_cannot_inherit_npc_register(self):
        cfg = review.profiles()
        role = {"roles": ["player_option"], "nodes": ["Node050"],
                "lines": ["784: NOption(266, Node056, 4);"]}
        details = review.context_background(
            "qhprzrch", 266, "your epitaph", role, cfg, [])
        self.assertIn("PLAYER character", details)
        self.assertIn("NPC 말투 지정 금지", details)
        self.assertNotIn("대통령으로서 권위적인", details)

    def test_real_richardson_ssl_nodes_and_roles(self):
        body = review.current_script_text("scripts_src/main/qhprzrch.ssl")
        refs = review.ssl_evidence(body, {250, 266, 276})
        self.assertIn("npc_reply", refs[250]["roles"])
        self.assertIn("Node045", refs[250]["nodes"])
        self.assertIn("player_option", refs[266]["roles"])
        self.assertIn("player_option", refs[276]["roles"])
        self.assertNotIn("npc_reply", refs[266]["roles"])

    def test_goris_mstr_reply_is_npc_not_unmapped(self):
        script = review.current_script_text("scripts_src/vault13/ocgoris.ssl")
        refs = review.ssl_evidence(script, {120, 122})
        self.assertIn("npc_reply", refs[120]["roles"])
        self.assertIn("npc_reply", refs[122]["roles"])
        self.assertIn("string_fragment", refs[120]["roles"])
        self.assertIn("Node003", refs[120]["nodes"])

    def test_script_comment_is_not_active_reply(self):
        script = ("procedure Node001 begin\n"
                  "// Reply(101);\nReply(102);\n"
                  "/* NOption(103, Node, 4); */\n"
                  "NOption(104, Node, 4);\nend\n")
        from contextual_review_queue import SCRIPT_BLOCK_COMMENT, SCRIPT_LINE_COMMENT
        import re
        script = SCRIPT_BLOCK_COMMENT.sub(
            lambda m: re.sub(r"[^\r\n]", " ", m.group()), script)
        script = SCRIPT_LINE_COMMENT.sub(
            lambda m: " " * len(m.group()), script)
        refs = review.ssl_evidence(script, {101, 102, 103, 104})
        self.assertEqual(refs[101]["roles"], ["unmapped"])
        self.assertEqual(refs[102]["roles"], ["npc_reply"])
        self.assertEqual(refs[103]["roles"], ["unmapped"])
        self.assertEqual(refs[104]["roles"], ["player_option"])

    def test_multi_role_is_quarantined(self):
        cfg = review.profiles()
        case = review.speaker_profile(
            "ocgoris", ["npc_reply", "player_option"], cfg)
        self.assertIn("AMBIGUOUS", case["speaker"])
        self.assertNotIn("하오체", case["register"])

    def test_glossary_matches_relevant_terms_only(self):
        cfg = review.profiles()
        result = review.glossary_for(
            "The vertibirds fly to Navarro.", cfg)
        self.assertEqual(result["Vertibird"], "버티버드")
        self.assertEqual(result["Navarro"], "나바로")
        self.assertNotIn("soap", result)
        flags = review.enforce_terms(
            "나바로의 수송기가 날아간다.", result, cfg)
        self.assertIn("glossary_violation:Vertibird->버티버드", flags)
        self.assertNotIn("glossary_violation:Navarro->나바로", flags)

    def test_unverified_output_is_not_applied(self):
        row = {"file": "data/text/korean/dialog/ahelder.msg",
               "msg_id": 999, "english": "Our world",
               "korean_current": "우리 세상", "context": "test"}
        a = review.result_key(row, [review.MODEL_HY])
        b = review.result_key(row, [review.MODEL_GEMMA])
        self.assertNotEqual(a, b)
        self.assertIn("placeholder_mismatch",
                      review.compare("아이템 %s 획득", "아이템 획득", "item"))
        self.assertIn("not_cp949",
                      review.compare("검수", "검수 🧪", "test"))

    def test_existing_reviewed_pair_is_stable_after_korean_edit(self):
        before = {
            "file": "data/text/korean/dialog/mcjo.msg",
            "msg_id": 159, "english": "Do you have a gold watch?",
            "korean_current": "금시계를 팔러 온 것은 아니지요?",
            "context": "Trader Jo's trade branch",
        }
        after = {**before, "korean_current": "혹시 판매하는 금시계가 있을까요?"}
        self.assertNotEqual(
            review.result_key(before, [review.MODEL_HY]),
            review.result_key(after, [review.MODEL_HY]),
        )
        existing = {
            "oldhash": {"file": before["file"], "id": before["msg_id"]},
        }
        visited = {(v["file"], v["id"]) for v in existing.values()}
        self.assertIn((after["file"], after["msg_id"]), visited)

    def test_journal_recovery_after_unwritten_checkpoint(self):
        row = {"key": "example-hash", "file": "data/text/korean/dialog/mcjo.msg",
               "msg_id": 159, "automatically_approved": False}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comparisons.jsonl"
            path.write_text(json.dumps(row) + "\n{incomplete", encoding="utf-8")
            state = {"completed": {}, "errors": {}, "model_mode": "both"}
            self.assertEqual(review.recover_journal(path, state), 1)
            self.assertEqual(
                state["completed"]["example-hash"]["id"], 159)
            self.assertEqual(review.recover_journal(path, state), 0)


if __name__ == "__main__":
    unittest.main()
