import importlib.util
from pathlib import Path
import unittest
src=Path(__file__).resolve().parents[1]/"audit_dialogue_register.py"
spec=importlib.util.spec_from_file_location("dialogue_register_auditor",src)
aud=importlib.util.module_from_spec(spec)
spec.loader.exec_module(aud)
class RegisterAuditTests(unittest.TestCase):
    def test_formality(self):
        assert aud.classify("\uC8C4\uC1A1\uD569\uB2C8\uB2E4.")=="formal"
        assert aud.classify("\uBC18\uAC11\uC2B5\uB2C8\uB2E4!")=="formal"
        assert aud.classify("\uAD1C\uCC2E\uC73C\uC138\uC694?")=="polite"
        assert aud.classify("\uBC18\uAC11\uC18C.")=="hao"
        assert aud.classify("\uBC18\uAC11\uB124.")=="plain"
        assert aud.classify("\uB124.")=="undetermined"
    def test_role_macros(self):
        data=b"Reply(101); NOption(102, Node3, 004); GOption(103, Node4, 004);"
        assert {int(x) for x in aud.NPC_RE.findall(data)}=={101}
        assert {int(x) for x in aud.PLAYER_RE.findall(data)}=={102,103}
    def test_cp949(self):
        raw=("{100}{VOX100}{\uC548\uB155\uD558\uC138\uC694.}\n"
             "{101}{}{\uC7A0\uAE50!}\n").encode("cp949")
        rows=list(aud.msg_rows(raw))
        assert rows[0]==(100,"VOX100","\uC548\uB155\uD558\uC138\uC694.")
        assert rows[1][1]==""
if __name__=="__main__":unittest.main()
