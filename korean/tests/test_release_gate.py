from pathlib import Path
import subprocess
import sys
import unittest

class ReleaseGateSafetyTests(unittest.TestCase):
    def test_public_upload_is_blocked_without_signed_off_review(self):
        root=Path(__file__).resolve().parents[2]
        code=root/"korean"/"release_gate.py"
        candidate=root/"korean-candidate-dist"
        packages=list(candidate.glob("*-Korean-Setup.zip")) if candidate.exists() else []
        archive=packages[0] if packages else root/"korean"/"release-approval.json"
        run=subprocess.run(
            [sys.executable,str(code),"--version","0.0.1","--run-id","123",
             "--archive",str(archive)],
            capture_output=True,text=True,
        )
        self.assertNotEqual(run.returncode,0)
        self.assertIn("not approved",run.stderr.lower())

if __name__=="__main__":
    unittest.main()
