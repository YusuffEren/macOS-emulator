import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from android_simulator import agent, macros, recording
from android_simulator.config import Toolchain, macros_root
from android_simulator.errors import AndroidSimError
from android_simulator.util import save_json


def _toolchain() -> Toolchain:
    return Toolchain(*(Path("tool") for _ in range(5)))


def _write_macro(name: str, steps: list[dict]) -> None:
    save_json(macros_root() / f"{name}.json", {"version": 1, "name": name, "steps": steps})


class RecordingTests(unittest.TestCase):
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

    def test_record_session_captures_executed_actions(self):
        recording.start("daily", notes="login flow")
        self.assertEqual(recording.status()["recording"], True)
        with patch("android_simulator.agent.adb_module.shell") as shell:
            agent.execute(_toolchain(), "emulator-5554", agent.Action("tap", {"x": 540, "y": 1200}, "open menu"))
            agent.execute(_toolchain(), "emulator-5554", agent.Action("swipe", {"x1": 540, "y1": 1600, "x2": 540, "y2": 400}))
        self.assertEqual(recording.status()["steps"], 2)
        saved = recording.stop()
        self.assertEqual(saved["steps"], 2)
        self.assertEqual(saved["contains_typed_text"], False)
        self.assertFalse(recording.session_path().exists())
        listed = macros.list_macros()
        self.assertEqual(listed[0]["name"], "daily")
        self.assertEqual(listed[0]["steps"], 2)

    def test_recorded_macro_replays_through_run_macro(self):
        recording.start("daily")
        with patch("android_simulator.agent.adb_module.shell"):
            agent.execute(_toolchain(), "emulator-5554", agent.Action("tap", {"x": 1, "y": 2}))
        recording.stop()
        with patch("android_simulator.macros.agent.execute") as execute:
            result = macros.run_macro(_toolchain(), "emulator-5556", "daily")
        self.assertEqual(result["serial"], "emulator-5556")
        self.assertEqual(result["executed_steps"], 1)
        execute.assert_called_once()

    def test_recording_flags_typed_text(self):
        recording.start("login")
        with patch("android_simulator.agent.adb_module.shell"):
            agent.execute(_toolchain(), "emulator-5554", agent.Action("type", {"text": "hunter2"}))
        self.assertEqual(recording.status()["contains_typed_text"], True)
        saved = recording.stop()
        self.assertEqual(saved["contains_typed_text"], True)

    def test_start_refuses_second_session(self):
        recording.start("first")
        with self.assertRaises(AndroidSimError):
            recording.start("second")
        recording.cancel()

    def test_stop_empty_and_cancel_discard(self):
        recording.start("empty")
        with self.assertRaises(AndroidSimError):
            recording.stop()
        result = recording.cancel()
        self.assertEqual(result["steps_discarded"], 0)
        with self.assertRaises(AndroidSimError):
            recording.cancel()

    def test_actions_are_not_recorded_without_session(self):
        with patch("android_simulator.agent.adb_module.shell"):
            result = agent.execute(_toolchain(), "emulator-5554", agent.Action("tap", {"x": 1, "y": 2}))
        self.assertEqual(result["executed"], True)
        self.assertFalse(recording.session_path().exists())
        self.assertEqual(recording.status(), {"recording": False})


class FanoutTests(unittest.TestCase):
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

    def test_fanout_replays_on_every_serial(self):
        _write_macro(
            "daily",
            [
                {"action": "tap", "arguments": {"x": 1, "y": 2}},
                {"action": "wait", "arguments": {"seconds": 0}},
            ],
        )
        with patch("android_simulator.macros.agent.execute") as execute:
            result = macros.run_macro_fanout(
                _toolchain(),
                ["emulator-5554", "emulator-5556"],
                "daily",
            )
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(execute.call_count, 4)
        self.assertEqual([item["serial"] for item in result["targets"]], ["emulator-5554", "emulator-5556"])

    def test_fanout_stops_on_first_error_by_default(self):
        _write_macro("daily", [{"action": "tap", "arguments": {"x": 1, "y": 2}}])
        with patch("android_simulator.macros.agent.execute") as execute:
            execute.side_effect = AndroidSimError("device disconnected")
            with self.assertRaises(AndroidSimError) as context:
                macros.run_macro_fanout(_toolchain(), ["emulator-5554", "emulator-5556"], "daily")
        self.assertIn("emulator-5554", str(context.exception))

    def test_fanout_continue_on_error_reports_failures(self):
        _write_macro("daily", [{"action": "tap", "arguments": {"x": 1, "y": 2}}])
        calls: list[str] = []

        def fake_execute(toolchain, serial, action, *, confirmed=False):
            calls.append(serial)
            if serial == "emulator-5554":
                raise AndroidSimError("device disconnected")

        with patch("android_simulator.macros.agent.execute", side_effect=fake_execute):
            result = macros.run_macro_fanout(
                _toolchain(),
                ["emulator-5554", "emulator-5556"],
                "daily",
                continue_on_error=True,
            )
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(calls, ["emulator-5554", "emulator-5556"])

    def test_fanout_sensitive_preflight_runs_before_any_device(self):
        _write_macro(
            "risky",
            [{"action": "tap", "arguments": {"x": 1, "y": 2}, "description": "Purchase item"}],
        )
        with patch("android_simulator.macros.agent.execute") as execute:
            with self.assertRaises(AndroidSimError):
                macros.run_macro_fanout(_toolchain(), ["emulator-5554", "emulator-5556"], "risky")
        execute.assert_not_called()

    def test_fanout_rejects_duplicate_and_invalid_serials(self):
        _write_macro("daily", [{"action": "tap", "arguments": {"x": 1, "y": 2}}])
        with self.assertRaises(AndroidSimError):
            macros.run_macro_fanout(_toolchain(), ["emulator-5554", "emulator-5554"], "daily")
        with self.assertRaises(AndroidSimError):
            macros.run_macro_fanout(_toolchain(), ["bad serial!"], "daily")
        with self.assertRaises(AndroidSimError):
            macros.run_macro_fanout(_toolchain(), [], "daily")


if __name__ == "__main__":
    unittest.main()
