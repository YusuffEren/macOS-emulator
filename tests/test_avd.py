from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from android_simulator.avd import _wifi_netsim_args, clone_avd, configure_avd, rename_avd
from android_simulator.config import Toolchain
from android_simulator.util import save_json
from android_simulator.errors import AndroidSimError


class AvdTests(unittest.TestCase):
    def test_wifi_args_quote_spaces(self) -> None:
        value = _wifi_netsim_args("Tempera WiFi", "password123")
        self.assertIn("--wifi", value)
        self.assertIn("Tempera WiFi", value)
        self.assertIn("password123", value)

    def test_wifi_password_minimum(self) -> None:
        with self.assertRaises(AndroidSimError):
            _wifi_netsim_args("ssid", "short")

    def test_configure_avd_preserves_and_updates_ini(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = root / "demo.avd" / "config.ini"
            config.parent.mkdir(parents=True)
            config.write_text("existing.key=keep\nhw.ramSize=1024\n", encoding="utf-8")
            with patch("android_simulator.avd.avd_home", return_value=root):
                configure_avd("demo", ram_mb=4096, data_gb=16, play_store=True)
            text = config.read_text(encoding="utf-8")
            self.assertIn("existing.key=keep", text)
            self.assertIn("hw.ramSize=4096", text)
            self.assertIn("disk.dataPartition.size=16G", text)
            self.assertIn("PlayStore.enabled=true", text)

    def test_clone_rewrites_avd_paths_and_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            avd_root = root / "avd"
            state_root = root / "state"
            source = avd_root / "source.avd"
            source.mkdir(parents=True)
            (source / "config.ini").write_text(
                "AvdId=source\navd.ini.displayname=source\n", encoding="utf-8"
            )
            (avd_root / "source.ini").write_text(
                f"path={source}\npath.rel=avd/source.avd\n", encoding="utf-8"
            )
            metadata_path = state_root / "instances" / "source.json"
            save_json(
                metadata_path,
                {
                    "name": "source",
                    "profile": "play",
                    "api": 35,
                    "arch": "arm64-v8a",
                    "device_profile": "pixel_8",
                    "ram_mb": 4096,
                    "data_gb": 16,
                    "instance_uuid": "old",
                },
            )
            toolchain = Toolchain(*(Path("tool") for _ in range(5)))
            with (
                patch.dict("os.environ", {"ANDROID_SIM_HOME": str(state_root)}),
                patch("android_simulator.avd.avd_home", return_value=avd_root),
                patch("android_simulator.avd.list_avds", return_value=["source"]),
                patch("android_simulator.avd._running_serial_for_avd", return_value=None),
            ):
                result = clone_avd(toolchain, "source", "copy")
            self.assertEqual(result["name"], "copy")
            self.assertNotEqual(result["instance_uuid"], "old")
            self.assertIn("AvdId=copy", (avd_root / "copy.avd" / "config.ini").read_text())
            self.assertIn("copy.avd", (avd_root / "copy.ini").read_text())

    def test_rename_moves_avd_and_preserves_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            avd_root = root / "avd"
            state_root = root / "state"
            source = avd_root / "source.avd"
            source.mkdir(parents=True)
            (source / "config.ini").write_text(
                "AvdId=source\navd.ini.displayname=source\n", encoding="utf-8"
            )
            (avd_root / "source.ini").write_text(
                f"path={source}\npath.rel=avd/source.avd\n", encoding="utf-8"
            )
            metadata_path = state_root / "instances" / "source.json"
            save_json(metadata_path, {"name": "source", "instance_uuid": "stable"})
            toolchain = Toolchain(*(Path("tool") for _ in range(5)))
            with (
                patch.dict("os.environ", {"ANDROID_SIM_HOME": str(state_root)}),
                patch("android_simulator.avd.avd_home", return_value=avd_root),
                patch("android_simulator.avd.list_avds", return_value=["source"]),
                patch("android_simulator.avd._running_serial_for_avd", return_value=None),
            ):
                result = rename_avd(toolchain, "source", "renamed")
            self.assertEqual(result["instance_uuid"], "stable")
            self.assertFalse(source.exists())
            self.assertTrue((avd_root / "renamed.avd").is_dir())
            self.assertIn("AvdId=renamed", (avd_root / "renamed.avd" / "config.ini").read_text())
            self.assertTrue((state_root / "instances" / "renamed.json").is_file())


if __name__ == "__main__":
    unittest.main()
