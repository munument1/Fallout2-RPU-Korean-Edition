import importlib.util
from pathlib import Path
import unittest


FILE = Path(__file__).resolve().parents[1] / "benchmark_translation_specialists.py"
spec = importlib.util.spec_from_file_location("rpu_mt_benchmark", FILE)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class TranslationBenchmarkTests(unittest.TestCase):
    def test_gold100_is_deterministic(self):
        rows = list(bench.historical_100_cases())
        self.assertEqual(len(rows), 100)
        self.assertEqual(len({(r["file"].split("-")[0], r["id"]) for r in rows}), 100)
        self.assertTrue(all(r["english"] and r["gold"] for r in rows))

    def test_translation_prompt_has_no_gold(self):
        english = "An example with a custom protected English token XYZ."
        for model in ("translategemma:12b", "hf.co/tencent/Hy-MT2-7B-GGUF:Q8_0"):
            prompt = bench.prompt(model, english)
            self.assertIn(english, prompt)
            self.assertIn("Korean", prompt)
            self.assertNotIn("verified_korean", prompt)


if __name__ == "__main__":
    unittest.main()
