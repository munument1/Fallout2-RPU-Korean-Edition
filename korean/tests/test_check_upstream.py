import importlib.util
from pathlib import Path
import unittest

source=Path(__file__).resolve().parent.parent/"check_upstream.py"
spec=importlib.util.spec_from_file_location("korean_check_upstream",source)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class KoreanReviewTest(unittest.TestCase):
    def test_msg_ids(self):
        a=b"{101}{}{Hello}\r\n{102}{}{Keep}\r\n{104}{}{Gone}"
        b=b"{101}{}{Hello changed}\n{102}{}{Keep}\n{103}{}{New}"
        k=b"{101}{}{\xb0\xa1}\n{102}{}{\xb0\xa1}"
        rows=m.compare_msg(a,b,k)
        self.assertEqual([(x["id"],x["kind"]) for x in rows],
                         [("101","modified"),("103","added"),("104","removed")])
        self.assertEqual([x["has_korean_id"] for x in rows],[True,False,False])

    def test_ettu_mod_path_mapping(self):
        e={"path":"Fallout2/Fallout1in2/data/text/korean/dialog/ABEL.msg"}
        match,candidates=m.matching_korean("Fallout2/Fallout1in2/mods/fo1_base/text/english/dialog/ABEL.msg",[e])
        self.assertEqual(match,e)

    def test_ambiguous_paths_not_guessed(self):
        e={"path":"appearance/hfr00s00/text/korean/game/foo.msg"}
        f={"path":"appearance/hmr00s00/text/korean/game/foo.msg"}
        match,candidates=m.matching_korean("appearance/source/text/english/game/foo.msg",[e,f])
        self.assertIsNone(match)
        self.assertEqual(len(candidates),2)

    def test_raw_msg_cp949_supported(self):
        msg=b"{0005}{}{\\xB0\\xA1}"
        self.assertIn("5",m.entries(msg))
