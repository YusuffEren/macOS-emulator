from __future__ import annotations

import unittest

from android_simulator.cli import build_parser


class CliTests(unittest.TestCase):
    def test_create_parser(self) -> None:
        args = build_parser().parse_args(["create", "--profile", "play", "--api", "37"])
        self.assertEqual(args.command, "create")
        self.assertEqual(args.profile, "play")
        self.assertEqual(args.api, 37)

    def test_network_parser(self) -> None:
        args = build_parser().parse_args(["network", "wifi", "on"])
        self.assertEqual(args.network_command, "wifi")
        self.assertEqual(args.state, "on")

    def test_instance_update_parser(self) -> None:
        args = build_parser().parse_args(["instance", "update", "demo", "fps=120"])
        self.assertEqual(args.instance_command, "update")
        self.assertEqual(args.assignments, ["fps=120"])

    def test_instance_batch_start_parser(self) -> None:
        args = build_parser().parse_args(["instance", "batch-start", "one", "two", "--headless"])
        self.assertEqual(args.names, ["one", "two"])
        self.assertTrue(args.headless)


if __name__ == "__main__":
    unittest.main()
