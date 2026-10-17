from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import hashlib,importlib.util,json
import unittest

spec=importlib.util.spec_from_file_location("combined_installer",
        Path(__file__).resolve().parent.parent/"combined_installer.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CombinedInstallerTests(unittest.TestCase):
    def fixtures(self,temp:Path,files=None):
        files=files or {"data/text/korean/dialog/test.msg":b"{100}{}{sample}"}
        archive=temp/"overlay.zip"
        with ZipFile(archive,"w") as zip:
            for path,body in files.items():zip.writestr(path,body)
        cfg={"schema":1,"game":"rpu","file_count":len(files),
             "zip_sha256":mod.digest(archive.read_bytes()),
             "engine_url":"https://github.com/munument1/Fallout2-Korean-Text-Engine/releases/download/v1.2.0-beta.2/Fallout2-Korean-Native-Setup.exe",
             "engine_sha256":"0223b962000683da6cb2dfe284f17f96036ffd102ce2cc0f053d41201fdbd1b7"}
        file=temp/"config.json"
        file.write_text(json.dumps(cfg),encoding="utf8")
        return file,archive
    def test_archive_validation_and_rollback(self):
        with TemporaryDirectory() as d:
            temp=Path(d)
            config,archive=self.fixtures(temp)
            cfg,members=mod.config_bundle(config,archive)
            target=temp/"RPU"
            target.mkdir()
            (target/"data").mkdir()
            (target/"fallout2.exe").write_bytes(b"fake")
            old=target/"data"/"text"/"korean"/"dialog"/"test.msg"
            old.parent.mkdir(parents=True)
            old.write_bytes(b"original")
            self.assertEqual(mod.install_translations(target,members,cfg),1)
            self.assertEqual(old.read_bytes(),b"{100}{}{sample}")
            self.assertEqual(mod.restore_translations(target),1)
            self.assertEqual(old.read_bytes(),b"original")
            self.assertFalse((target/mod.TEXT_BACKUP).exists())
    def test_reject_unexpected_binary_and_parent(self):
        with TemporaryDirectory() as d:
            temp=Path(d)
            for path in ("../../outside.txt","data/program.exe"):
                config,archive=self.fixtures(temp,{path:b"bad"})
                with self.assertRaises(ValueError):
                    mod.config_bundle(config,archive)
    def test_engine_manifest_requires_fully_patched_file(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            patched=root/"fallout2.exe"
            patched.write_bytes(b"patched-data")
            backup=root/mod.ENGINE_BACKUP
            backup.mkdir()
            (backup/"manifest.json").write_text(json.dumps({"after":{"fallout2.exe":mod.digest(patched.read_bytes())}}),encoding="utf8")
            self.assertTrue(mod.verified_engine(root))
            patched.write_bytes(b"altered")
            self.assertFalse(mod.verified_engine(root))
    def test_user_edits_are_not_overwritten_on_restore(self):
        with TemporaryDirectory() as d:
            temp=Path(d)
            config,archive=self.fixtures(temp)
            cfg,members=mod.config_bundle(config,archive)
            root=temp/"RPU"
            root.mkdir()
            mod.install_translations(root,members,cfg)
            target=root/"data"/"text"/"korean"/"dialog"/"test.msg"
            target.write_bytes(b"my-edits")
            with self.assertRaises(ValueError):
                mod.restore_translations(root)
            self.assertEqual(target.read_bytes(),b"my-edits")

if __name__=="__main__":
    unittest.main()
