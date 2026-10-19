import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from android_simulator import macros, planner
from android_simulator.cli import main
from android_simulator.errors import AndroidSimError


def _response(steps):
    return {"schema_version": 1, "steps": steps}


class PlannerTests(unittest.TestCase):
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

    def test_add_list_remove_round_trip(self):
        planner.add("local", "http://127.0.0.1:8080/plan", api_key_env="LOCAL_KEY", model="test-model")
        listed = planner.list_planners()
        self.assertEqual(listed[0]["name"], "local")
        self.assertEqual(listed[0]["api_key_env"], "LOCAL_KEY")
        self.assertEqual(planner.remove("local"), {"removed": "local"})
        self.assertEqual(planner.list_planners(), [])

    def test_add_refuses_remote_http_and_duplicates(self):
        with self.assertRaises(AndroidSimError):
            planner.add("remote", "http://example.com/plan")
        planner.add("remote", "https://example.com/plan")
        with self.assertRaises(AndroidSimError):
            planner.add("remote", "https://other.example.com/plan")

    def test_plan_saves_validated_macro(self):
        planner.add("local", "https://example.com/plan")
        captured = {}

        def fake_transport(endpoint, payload, *, headers, timeout_seconds):
            captured["endpoint"] = endpoint
            captured["payload"] = payload
            captured["headers"] = headers
            return _response([{"action": "tap", "arguments": {"x": 540, "y": 1200}, "description": "open menu"}])

        result = planner.plan("local", "open the menu", transport=fake_transport)
        self.assertEqual(captured["endpoint"], "https://example.com/plan")
        self.assertIn("tap", captured["payload"]["allowed_actions"])
        self.assertEqual(result["saved_as"], "open-the-menu")
        self.assertEqual(result["steps"], 1)
        self.assertFalse(result["requires_confirmation"])
        listed = macros.list_macros()
        self.assertEqual(listed[0]["name"], "open-the-menu")

    def test_plan_requires_missing_api_key_env(self):
        os.environ.pop("MY_PLANNER_KEY", None)
        planner.add("secure", "https://example.com/plan", api_key_env="MY_PLANNER_KEY")
        with self.assertRaises(AndroidSimError) as context:
            planner.plan("secure", "goal", transport=lambda *a, **k: _response([]))
        self.assertIn("MY_PLANNER_KEY", str(context.exception))

    def test_plan_sends_bearer_token_from_env(self):
        os.environ["MY_PLANNER_KEY"] = "secret-token"
        try:
            planner.add("secure", "https://example.com/plan", api_key_env="MY_PLANNER_KEY")
            captured = {}

            def fake_transport(endpoint, payload, *, headers, timeout_seconds):
                captured["headers"] = headers
                return _response([{"action": "home", "arguments": {}}])

            planner.plan("secure", "go home", transport=fake_transport)
            self.assertEqual(captured["headers"].get("Authorization"), "Bearer secret-token")
        finally:
            del os.environ["MY_PLANNER_KEY"]

    def test_plan_rejects_disallowed_action(self):
        planner.add("local", "https://example.com/plan")

        def fake_transport(endpoint, payload, *, headers, timeout_seconds):
            return _response([{"action": "shell", "arguments": {"command": "rm -rf /"}}])

        with self.assertRaises(AndroidSimError):
            planner.plan("local", "destructive goal", transport=fake_transport)
        self.assertEqual(macros.list_macros(), [])

    def test_plan_rejects_bad_schema_version(self):
        planner.add("local", "https://example.com/plan")

        def fake_transport(endpoint, payload, *, headers, timeout_seconds):
            return {"schema_version": 2, "steps": [{"action": "home", "arguments": {}}]}

        with self.assertRaises(AndroidSimError):
            planner.plan("local", "goal", transport=fake_transport)

    def test_plan_flags_sensitive_and_typed_steps(self):
        planner.add("local", "https://example.com/plan")

        def fake_transport(endpoint, payload, *, headers, timeout_seconds):
            return _response(
                [
                    {"action": "type", "arguments": {"text": "hello"}, "description": "Purchase item"},
                    {"action": "wait", "arguments": {"seconds": 0}},
                ]
            )

        result = planner.plan("local", "buy the item", save_as="risky", transport=fake_transport)
        self.assertTrue(result["requires_confirmation"])
        self.assertTrue(result["contains_typed_text"])

    def test_plan_refuses_overwrite_without_force(self):
        planner.add("local", "https://example.com/plan")

        def fake_transport(endpoint, payload, *, headers, timeout_seconds):
            return _response([{"action": "home", "arguments": {}}])

        planner.plan("local", "go home", save_as="daily", transport=fake_transport)
        with self.assertRaises(AndroidSimError):
            planner.plan("local", "go home again", save_as="daily", transport=fake_transport)
        planner.plan("local", "go home again", save_as="daily", force=True, transport=fake_transport)

    def test_plan_wraps_transport_errors(self):
        from android_simulator.errors import AndroidSimError as SimError

        planner.add("local", "https://example.com/plan")

        def fake_transport(endpoint, payload, *, headers, timeout_seconds):
            raise SimError("Planner endpoint returned HTTP 500")

        with self.assertRaises(SimError):
            planner.plan("local", "goal", transport=fake_transport)

    def test_json_envelope_for_planner_list(self):
        import contextlib
        import io

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--json", "planner", "list"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"], [])


if __name__ == "__main__":
    unittest.main()
