from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from android_simulator import engine


REPO_ROOT = Path(__file__).resolve().parent.parent


class EngineTests(unittest.TestCase):
    def test_committed_source_lock_is_self_consistent(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "engine" / "verify-lock.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        summary = json.loads(result.stdout)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["frozen_projects"], 76)

    def test_installation_requires_matching_receipt_and_binary_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = root / "current"
            current.mkdir()
            emulator = current / "emulator"
            emulator.write_bytes(b"verified engine")
            lock_path = REPO_ROOT / "engine" / "engine.lock.json"
            lock_value = json.loads(lock_path.read_text(encoding="utf-8"))
            receipt = {
                "schema_version": 1,
                "lock_id": lock_value["lock_id"],
                "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
                "files": [
                    {
                        "path": "emulator",
                        "sha256": hashlib.sha256(emulator.read_bytes()).hexdigest(),
                    }
                ],
            }
            (current / "build-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            with patch("android_simulator.engine.engine_root", return_value=root):
                self.assertTrue(engine.installation()["valid"])
                emulator.write_bytes(b"tampered")
                invalid = engine.installation()
            self.assertFalse(invalid["valid"])
            self.assertEqual(invalid["reason"], "emulator_digest_mismatch")

    def test_custom_engine_is_never_selected_on_unsupported_host(self) -> None:
        with (
            patch("android_simulator.engine.platform.system", return_value="Windows"),
            patch("android_simulator.engine.installation", return_value={"valid": True, "emulator": "engine"}),
        ):
            self.assertIsNone(engine.custom_emulator())


if __name__ == "__main__":
    unittest.main()
