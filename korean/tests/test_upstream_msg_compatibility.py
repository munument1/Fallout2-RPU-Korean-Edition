"""Guard the hand-reviewed upstream MSG compatibility adjustments."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def msg(name, group="dialog"):
    return (ROOT / "data" / "text" / "korean" / group / name).read_bytes().decode("cp949")


def rows(content):
    result = {}
    for number, tag, body in re.findall(r"(?m)^\{(\d+)\}\{([^}]*)\}\{([^}]*)\}", content):
        number = int(number)
        if number in result:
            raise ValueError(f"Duplicate MSG ID {number}")
        result[number] = (tag, body)
    return result


class UpstreamMessageCompatibilityTests(unittest.TestCase):
    def test_rebecca_tamper_warnings_present(self):
        entries = rows(msg("dcrebecc.msg"))
        for id in range(1230, 1235):
            self.assertIn(id, entries)
            self.assertFalse(entries[id][0])
            self.assertTrue(re.search(r"[가-힣]", entries[id][1]))

    def test_molerat_rename_reuses_existing_translation(self):
        old = msg("vilrat.msg")
        new = msg("zclvillrat.msg")
        self.assertEqual(old, new)
        self.assertEqual(set(rows(new)), {100, 101, 102, 200})

    def test_combat_gender_metadata_retained(self):
        pc = set(range(250,259)) | set(range(261,273)) | {559}
        pc |= set(range(561,566)) | set(range(570,579)) | {583,584}
        npc = {400,401,406,407,408,418,420,421,422,708,709}
        npc |= set(range(711,716)) | set(range(720,729)) | {733,734}
        self.assertEqual((len(pc), len(npc)), (38, 27))
        entries = rows(msg("combat.msg", "game"))
        for id in pc:
            self.assertEqual(entries[id][0], "female_pc", id)
        for id in npc:
            self.assertEqual(entries[id][0], "female_npc", id)
        self.assertEqual(Counter(tag for tag, body in entries.values() if tag),
                         Counter({"female_pc": 38, "female_npc": 27}))

    def test_editor_metadata_and_changed_dialogue(self):
        self.assertEqual(rows(msg("editor.msg", "game"))[304][0], "editor")
        self.assertIn("그 옷에", rows(msg("ectrappr.msg"))[102][1])
        epa = rows(msg("epac6.msg"))
        for id in (280,300):
            self.assertIn("창고에", epa[id][1])

    def test_review_files_have_manifest_hashes(self):
        manifest = json.loads((ROOT / "korean/manifest.json").read_text(encoding="utf-8"))
        names = {
            "data/text/korean/dialog/dcrebecc.msg",
            "data/text/korean/dialog/zclvillrat.msg",
            "data/text/korean/dialog/ectrappr.msg",
            "data/text/korean/dialog/epac6.msg",
            "data/text/korean/game/combat.msg",
            "data/text/korean/game/editor.msg",
        }
        files = {row["path"]: row for row in manifest["files"]}
        for name in names:
            row = files[name]
            content = (ROOT / name).read_bytes()
            self.assertEqual(len(content), row["bytes"], name)
            self.assertEqual(hashlib.sha256(content).hexdigest(), row["sha256"], name)
        self.assertEqual(len(manifest["files"]), 1341)


if __name__ == "__main__":
    unittest.main()
