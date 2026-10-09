import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from dependencies import BASE, LOCK, DependencyError, resolve, validate


class DependencyBehavior(unittest.TestCase):
    def test_official_sources_and_required_resources(self):
        world, brain = resolve()
        self.assertNotIn(BASE, world.parents)
        self.assertNotIn(BASE, brain.parents)
        self.assertEqual(json.loads((brain / "package.json").read_text(encoding="utf-8"))["version"], "0.8.1")
        # PR #14 was the vendored edit to spatial.py; official archive is intact.
        self.assertTrue((world / "LICENSE").is_file())

    def test_missing_or_modified_dependencies_fail_actionably(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(DependencyError, "setup.ps1"):
                validate("lingshu", root)
            source = root / ("lingshu-" + LOCK["lingshu"]["commit"])
            source.mkdir()
            (source / ".source-manifest.json").write_text(json.dumps({"commit": LOCK["lingshu"]["commit"], "archive_sha256": LOCK["lingshu"]["sha256"], "files": {"bad.py": "wrong"}}), encoding="utf-8")
            (source / "bad.py").write_text("modified", encoding="utf-8")
            with self.assertRaisesRegex(DependencyError, "上游文件缺失或已修改"):
                validate("lingshu", root)
            env = {**os.environ, "LINGSHU_LAB_DEPENDENCIES": temp}
            result = subprocess.run([sys.executable, "-X", "utf8", "-c", "import workbench"], cwd=BASE, env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("setup.ps1", result.stderr)
            self.assertNotIn("vendor", result.stderr)

