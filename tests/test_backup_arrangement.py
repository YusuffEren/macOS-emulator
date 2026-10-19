import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from android_simulator import arrangement, avd, backup, settings
from android_simulator.cli import main
from android_simulator.config import Toolchain, avd_home, instance_metadata_path
from android_simulator.errors import AndroidSimError
from android_simulator.util import save_json


def _toolchain() -> Toolchain:
    return Toolchain(*(Path("tool") for _ in range(5)))


def _make_instance(root: Path, name: str) -> None:
    avd_dir = avd_home() / f"{name}.avd"
    avd_dir.mkdir(parents=True)
    (avd_dir / "config.ini").write_text("AvdId=old\nhw.ramSize=4096\n", encoding="utf-8")
    (avd_dir / "userdata-qemu.img").write_bytes(b"userdata" * 128)
    (avd_dir / "snapshots").mkdir()
    (avd_dir / "snapshots" / "default_boot.img").write_bytes(b"snapshot" * 64)
    (avd_home() / f"{name}.ini").write_text(f"path={avd_dir}\n", encoding="utf-8")
    save_json(
        instance_metadata_path(name),
        {"name": name, "profile": "play", "api": 36, "ram_mb": 4096, "data_gb": 16},
    )


class BackupArrangementTests(unittest.TestCase):
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
        self.running = patch("android_simulator.backup.avd_module._running_serial_for_avd", return_value=None)
        self.running.start()
        self.list_avds = patch("android_simulator.backup.avd_module.list_avds", return_value=[])
        self.list_avds.start()

    def tearDown(self):
        self.list_avds.stop()
        self.running.stop()
        self.environment.stop()
        self.temporary.cleanup()

    def test_backup_round_trip_restores_files_and_identity(self):
        _make_instance(self.root, "phone")
        created = backup.create(_toolchain(), "phone", notes="before update")
        backup_id = created["backup_id"]
        self.assertTrue((self.root / "state" / "backups" / backup_id / "manifest.json").is_file())
        self.assertEqual(created["file_count"], 5)

        # Simulate losing the instance, then restore it.
        import shutil

        shutil.rmtree(avd_home() / "phone.avd")
        (avd_home() / "phone.ini").unlink()
        metadata = backup.restore(_toolchain(), backup_id)
        self.assertEqual(metadata["name"], "phone")
        self.assertEqual(metadata["restored_from"], backup_id)
        self.assertNotEqual(metadata["instance_uuid"], "")
        restored_ini = (avd_home() / "phone.ini").read_text(encoding="utf-8")
        self.assertIn("phone.avd", restored_ini)
        restored_config = (avd_home() / "phone.avd" / "config.ini").read_text(encoding="utf-8")
        self.assertIn("AvdId=phone", restored_config)
        self.assertEqual(
            (avd_home() / "phone.avd" / "userdata-qemu.img").read_bytes(),
            b"userdata" * 128,
        )

    def test_backup_create_refuses_running_instance(self):
        _make_instance(self.root, "phone")
        with patch("android_simulator.backup.avd_module._running_serial_for_avd", return_value="emulator-5554"):
            with self.assertRaises(AndroidSimError):
                backup.create(_toolchain(), "phone")

    def test_restore_refuses_existing_target(self):
        _make_instance(self.root, "phone")
        created = backup.create(_toolchain(), "phone")
        with patch("android_simulator.backup.avd_module.list_avds", return_value=["phone"]):
            with self.assertRaises(AndroidSimError):
                backup.restore(_toolchain(), created["backup_id"])
        restored = backup.restore(_toolchain(), created["backup_id"], name="phone-copy")
        self.assertEqual(restored["name"], "phone-copy")

    def test_restore_detects_tampered_backup(self):
        _make_instance(self.root, "phone")
        created = backup.create(_toolchain(), "phone")
        tampered = self.root / "state" / "backups" / created["backup_id"] / "avd" / "userdata-qemu.img"
        tampered.write_bytes(b"tampered")
        with self.assertRaises(AndroidSimError):
            backup.restore(_toolchain(), created["backup_id"])

    def test_verify_reports_missing_file(self):
        _make_instance(self.root, "phone")
        created = backup.create(_toolchain(), "phone")
        (self.root / "state" / "backups" / created["backup_id"] / "avd" / "snapshots" / "default_boot.img").unlink()
        report = backup.verify(created["backup_id"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("missing" in item for item in report["mismatches"]))

    def test_backup_delete_requires_confirmation_and_removes_directory(self):
        _make_instance(self.root, "phone")
        created = backup.create(_toolchain(), "phone")
        with self.assertRaises(AndroidSimError):
            backup.delete(created["backup_id"])
        result = backup.delete(created["backup_id"], confirmed=True)
        self.assertEqual(result["deleted"], created["backup_id"])
        self.assertFalse((self.root / "state" / "backups" / created["backup_id"]).exists())

    def test_backup_list_round_trip(self):
        self.assertEqual(backup.list_backups(), [])
        _make_instance(self.root, "phone")
        created = backup.create(_toolchain(), "phone")
        listed = backup.list_backups()
        self.assertEqual(listed[0]["backup_id"], created["backup_id"])
        self.assertEqual(listed[0]["instance"], "phone")
        self.assertEqual(listed[0]["bytes"], created["bytes"])

    def test_eco_mode_caps_refresh_rate(self):
        runtime = settings.validate({"fps": 120, "eco_mode": True})
        self.assertEqual(settings.effective_refresh_rate(runtime), 30)
        runtime = settings.validate({"fps": 120, "eco_mode": False})
        self.assertEqual(settings.effective_refresh_rate(runtime), 120)

    def test_eco_mode_change_requires_restart(self):
        _make_instance(self.root, "phone")
        result = settings.update("phone", {"eco_mode": True})
        self.assertIn("eco_mode", result["restart_fields"])

    def test_window_settings_validation(self):
        with self.assertRaises(AndroidSimError):
            settings.validate({"window_x": -5})
        runtime = settings.validate({"window_x": 100, "window_y": 200})
        self.assertEqual(runtime["window_x"], 100)

    def test_window_args_omitted_when_unset(self):
        self.assertEqual(avd.window_args(settings.validate({})), [])
        args = avd.window_args(settings.validate({"window_x": 100, "window_y": 200}))
        self.assertEqual(args, ["-window-x", "100", "-window-y", "200"])

    def test_arrangement_grid_and_persistence(self):
        _make_instance(self.root, "phone-a")
        _make_instance(self.root, "phone-b")
        _make_instance(self.root, "phone-c")
        placements = arrangement.plan(["phone-a", "phone-b", "phone-c"], columns=2)
        self.assertEqual([(p["row"], p["column"]) for p in placements], [(0, 0), (0, 1), (1, 0)])
        self.assertEqual(placements[1]["x"], arrangement.DEFAULT_ORIGIN_X + arrangement.DEFAULT_CELL_WIDTH + arrangement.DEFAULT_MARGIN)
        self.assertEqual(placements[2]["y"], arrangement.DEFAULT_ORIGIN_Y + arrangement.DEFAULT_CELL_HEIGHT + arrangement.DEFAULT_MARGIN)
        result = arrangement.apply(placements)
        self.assertTrue(result["applied"])
        self.assertTrue(all(item["restart_required"] for item in result["instances"]))
        self.assertEqual(settings.get("phone-b")["window_x"], placements[1]["x"])

    def test_arrangement_dry_run_does_not_persist(self):
        _make_instance(self.root, "phone-a")
        placements = arrangement.plan(["phone-a"])
        result = arrangement.apply(placements, dry_run=True)
        self.assertFalse(result["applied"])
        self.assertEqual(settings.get("phone-a")["window_x"], -1)

    def test_arrangement_rejects_unknown_instance(self):
        placements = arrangement.plan(["ghost"])
        with self.assertRaises(AndroidSimError):
            arrangement.apply(placements, dry_run=True)

    def test_json_envelope_for_backup_list(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--json", "backup", "list"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"], [])

    def test_json_envelope_for_arrange(self):
        _make_instance(self.root, "phone-a")
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--json", "instance", "arrange", "phone-a", "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["applied"], False)
        self.assertEqual(payload["data"]["plan"][0]["name"], "phone-a")


if __name__ == "__main__":
    unittest.main()
