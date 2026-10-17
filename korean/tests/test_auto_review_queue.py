import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "auto_review_queue.py"
spec = importlib.util.spec_from_file_location("rpu_auto_review", SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class LocalReviewQueueTests(unittest.TestCase):
    def test_msg_parser_with_voice_and_inline_comment(self):
        raw = (
            "{100}{VOX1}{안녕하세요.}\r\n"
            "{101}{}{이 줄은 맞아요.} # script annotation\r\n"
            "{102}{}{두 줄\r\n모두 유지합니다.}\r\n"
        ).encode("cp949")
        data, warnings = review.parse_msg(raw)
        self.assertEqual(warnings, [])
        self.assertEqual(list(data), [100, 101, 102])
        self.assertEqual(data[101]["text"], "이 줄은 맞아요.")
        self.assertEqual(data[102]["text"].count("\r\n"), 1)
        self.assertEqual(data[100]["voice"], "VOX1")

    def test_duplicate_id_is_not_silently_accepted(self):
        data, warnings = review.parse_msg(b"{100}{}{one}\n{100}{}{two}\n")
        self.assertEqual(len(data), 1)
        self.assertIn("duplicate_id:100", warnings)

    def test_invalid_suggestions_are_rejected(self):
        rows = [{"id": 100, "korean": "물건 %s을 받았습니다.",
                 "english": "You got an item.", "voice": ""}]
        answer = {"suggestions": [
            {"id": 100, "korean": "물건을 받았습니다.", "confidence": 0.99},
            {"id": 123, "korean": "임의 대사", "confidence": 0.99},
        ]}
        passed, rejected = review.safe_suggestions(answer, rows)
        self.assertEqual(passed, [])
        self.assertEqual(len(rejected), 2)

    def test_good_suggestion_is_queued_not_applied(self):
        rows = [{"id": 150, "korean": "검사로 갔습니다.",
                 "english": "I went to the doctor.", "voice": ""}]
        answer = {"suggestions": [
            {"id": 150, "korean": "의사에게 갔습니다.",
             "reason": "doctor is a person", "confidence": 0.98},
        ]}
        passed, rejected = review.safe_suggestions(answer, rows)
        self.assertEqual(rejected, [])
        self.assertEqual(passed[0]["status"], "needs_independent_verification")
        self.assertEqual(rows[0]["korean"], "검사로 갔습니다.")


if __name__ == "__main__":
    unittest.main()
