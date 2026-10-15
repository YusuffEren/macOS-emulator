import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from android_simulator import agent, controls, library, macros, maintenance, settings
from android_simulator.cli import main
from android_simulator.config import Toolchain
from android_simulator.errors import AndroidSimError
from android_simulator.util import save_json


class AirFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ,
            {
                "ANDROID_SIM_HOME": str(self.root / "state"),
                "ANDROID_AVD_HOME": str(self.root / "avd"),
            },
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def test_settings_migrate_and_report_restart(self):
        path = self.root / "state" / "instances" / "phone.json"
        save_json(path, {"name": "phone", "ram_mb": 3072, "data_gb": 16})
        result = settings.update("phone", {"fps": 120, "microphone": True})
        self.assertTrue(result["restart_required"])
        self.assertEqual(result["restart_fields"], ["fps"])
        self.assertTrue(path.with_suffix(".json.v0.bak").exists())

    def test_settings_reject_unknown_fps(self):
        with self.assertRaises(AndroidSimError):
            settings.validate({"fps": 75})

    def test_library_round_trip(self):
        library.add("com.example.game", "Example", favorite=True)
        self.assertEqual(library.list_apps()[0]["package"], "com.example.game")
        library.remove("com.example.game")
        self.assertEqual(library.list_apps(), [])

    def test_controls_require_normalized_coordinates(self):
        with self.assertRaises(AndroidSimError):
            controls.validate(
                {
                    "version": 1,
                    "package": "com.example.game",
                    "orientation": "landscape",
                    "mappings": [{"input": "W", "action": "tap", "point": [3, 4]}],
                }
            )

    def test_sensitive_agent_action_requires_confirmation(self):
        action = agent.Action("tap", {"x": 1, "y": 2}, "Confirm purchase")
        self.assertTrue(agent.requires_confirmation(action))

    def test_agent_audit_redacts_typed_text(self):
        action = agent.Action("type", {"text": "secret value"})
        toolchain = Toolchain(*(Path("tool") for _ in range(5)))
        with patch("android_simulator.agent.adb_module.shell"):
            agent.execute(toolchain, "emulator-5554", action)
        audit = (self.root / "state" / "logs" / "agent-audit.ndjson").read_text()
        self.assertNotIn("secret value", audit)
        self.assertIn("<redacted>", audit)

    def test_macro_import_and_sensitive_preflight(self):
        source = self.root / "macro.json"
        source.write_text(
            json.dumps(
                {
                    "version": 1,
                    "name": "daily",
                    "steps": [
                        {"action": "tap", "arguments": {"x": 1, "y": 2}, "description": "Purchase item"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        imported = macros.import_macro(source)
        self.assertEqual(imported["steps"], 1)
        self.assertEqual(macros.list_macros()[0]["name"], "daily")
        toolchain = Toolchain(*(Path("tool") for _ in range(5)))
        with self.assertRaises(AndroidSimError):
            macros.run_macro(toolchain, "emulator-5554", "daily")

    def test_disk_cleanup_requires_confirmation(self):
        with self.assertRaises(AndroidSimError):
            maintenance.clean(confirmed=False)

    def test_json_envelope_for_state_only_command(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--json", "library", "list"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"], [])

    def test_json_error_envelope(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--json", "library", "remove", "com.example.missing"])
        self.assertEqual(code, 2)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "android_sim_error")


if __name__ == "__main__":
    unittest.main()
