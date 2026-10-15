from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from pathlib import Path

from . import __version__
from . import adb as adb_module
from . import agent, apps, avd, controls, engine, library, macros, maintenance, media, network, settings
from .contract import Response, emit
from .config import DEFAULT_ARCH, DEFAULT_NAME, PROFILE_TAGS, discover_toolchain
from .doctor import print_doctor
from .errors import AndroidSimError
from .sdk import install_base_packages, list_packages
from .util import machine_output


def _add_serial(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--serial",
        default=os.environ.get("ANDROID_SIM_SERIAL"),
        help="ADB serial (defaults to the only running emulator)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="android-sim",
        description="Reproducible Android Emulator environments for Apple Silicon Macs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit the stable JSON response envelope")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check the Mac and Android SDK prerequisites")
    sub.add_parser("update-sdk", help="Install/update emulator, platform-tools, and command-line tools")
    sub.add_parser("images", help="List available ARM64 Android system images")
    sub.add_parser("list", help="List configured AVDs and connected devices")

    create = sub.add_parser("create", help="Create a new isolated Android virtual device")
    create.add_argument("--name", default=DEFAULT_NAME)
    create.add_argument("--profile", choices=sorted(PROFILE_TAGS), default="play")
    create.add_argument("--api", type=int, help="Android API level; defaults to newest supported stable candidate")
    create.add_argument("--arch", default=DEFAULT_ARCH)
    create.add_argument("--device", help="avdmanager hardware profile ID, such as pixel_8")
    create.add_argument("--ram-mb", type=int)
    create.add_argument("--data-gb", type=int, default=16)
    create.add_argument("--force", action="store_true", help="Replace an existing AVD with this name")

    start = sub.add_parser("start", help="Start an AVD and wait for Android to boot")
    start.add_argument("name", nargs="?", default=DEFAULT_NAME)
    start.add_argument("--cold", action="store_true", help="Ignore saved quick-boot snapshots")
    start.add_argument("--wipe", action="store_true", help="Factory reset before booting (destructive)")
    start.add_argument("--headless", action="store_true")
    start.add_argument("--no-audio", action="store_true")
    start.add_argument("--wifi-ssid", help="Custom simulated Wi-Fi SSID (Emulator 36.5+)")
    start.add_argument("--wifi-password", help="Optional WPA2 password; at least 8 characters")
    start.add_argument("--dns", help="Comma-separated DNS servers")
    start.add_argument("--proxy", help="Startup HTTP proxy URL or host:port")
    start.add_argument("--no-wait", action="store_true")
    start.add_argument("--timeout", type=int, default=240)
    start.add_argument(
        "--emulator-arg",
        action="append",
        default=[],
        help="Advanced: append one raw Android Emulator argument (repeatable)",
    )

    stop = sub.add_parser("stop", help="Stop a running emulator")
    _add_serial(stop)

    delete = sub.add_parser("delete", help="Delete an AVD and its persistent data")
    delete.add_argument("name")

    identity = sub.add_parser("identity", help="Show the current emulator identity diagnostics")
    _add_serial(identity)
    identity.add_argument("--json", dest="identity_json", action="store_true")

    fresh = sub.add_parser(
        "new-identity",
        help="Create a separate fresh AVD identity from an existing managed instance",
    )
    fresh.add_argument("source", nargs="?", default=DEFAULT_NAME)
    fresh.add_argument("--name")

    reset = sub.add_parser(
        "factory-reset",
        help="Wipe an AVD, clearing apps/accounts and generating fresh device state",
    )
    reset.add_argument("name", nargs="?", default=DEFAULT_NAME)
    reset.add_argument("--yes", action="store_true")
    reset.add_argument("--no-wait", action="store_true")

    install = sub.add_parser("install", help="Install one APK or a directory of split APKs")
    _add_serial(install)
    install.add_argument("paths", nargs="+", type=Path)
    install.add_argument("--no-replace", action="store_true")
    install.add_argument("--no-grant", action="store_true")
    install.add_argument("--test-only", action="store_true")

    install_url = sub.add_parser("install-url", help="Download an APK over HTTPS and install it")
    _add_serial(install_url)
    install_url.add_argument("url")
    install_url.add_argument("--sha256")
    install_url.add_argument("--allow-http", action="store_true")
    install_url.add_argument("--no-replace", action="store_true")
    install_url.add_argument("--no-grant", action="store_true")
    install_url.add_argument("--test-only", action="store_true")

    download = sub.add_parser("download", help="Download a file and place it in Android's Downloads folder")
    _add_serial(download)
    download.add_argument("url")
    download.add_argument("--filename")
    download.add_argument("--sha256")
    download.add_argument("--allow-http", action="store_true")

    play = sub.add_parser("play", help="Open an app listing in the official Google Play Store")
    _add_serial(play)
    play.add_argument("package", help="Android package name, for example com.spotify.music")

    launch = sub.add_parser("launch", help="Launch an installed package's main activity")
    _add_serial(launch)
    launch.add_argument("package")

    uninstall = sub.add_parser("uninstall", help="Uninstall a package")
    _add_serial(uninstall)
    uninstall.add_argument("package")
    uninstall.add_argument("--keep-data", action="store_true")

    app_list = sub.add_parser("apps", help="List installed app package names")
    _add_serial(app_list)
    app_list.add_argument("--all", action="store_true", help="Include system packages")

    shell_parser = sub.add_parser("shell", help="Run an adb shell command on the emulator")
    _add_serial(shell_parser)
    shell_parser.add_argument("args", nargs=argparse.REMAINDER)

    network_parser = sub.add_parser("network", help="Inspect or control simulated networking")
    _add_serial(network_parser)
    network_sub = network_parser.add_subparsers(dest="network_command", required=True)
    network_sub.add_parser("status")
    wifi = network_sub.add_parser("wifi")
    wifi.add_argument("state", choices=("on", "off"))
    speed = network_sub.add_parser("speed")
    speed.add_argument("preset")
    delay = network_sub.add_parser("delay")
    delay.add_argument("preset")
    proxy = network_sub.add_parser("proxy")
    proxy.add_argument("value", help="host:port or 'clear'")

    instance = sub.add_parser("instance", help="Clone and manage persistent instances")
    instance_sub = instance.add_subparsers(dest="instance_command", required=True)
    clone = instance_sub.add_parser("clone")
    clone.add_argument("source")
    clone.add_argument("name")
    instance_sub.add_parser("list")
    rename = instance_sub.add_parser("rename")
    rename.add_argument("source")
    rename.add_argument("name")
    instance_delete = instance_sub.add_parser("delete")
    instance_delete.add_argument("name")
    instance_update = instance_sub.add_parser("update")
    instance_update.add_argument("name")
    instance_update.add_argument("assignments", nargs="+")
    batch_start = instance_sub.add_parser("batch-start")
    batch_start.add_argument("names", nargs="+")
    batch_start.add_argument("--headless", action="store_true")
    batch_start.add_argument("--timeout", type=int, default=240)

    snapshot = sub.add_parser("snapshot", help="Manage quick-boot snapshots")
    _add_serial(snapshot)
    snapshot.add_argument("operation", choices=("list", "save", "load", "delete"))
    snapshot.add_argument("name", nargs="?")

    setting = sub.add_parser("settings", help="Read or update per-instance settings")
    setting_sub = setting.add_subparsers(dest="settings_command", required=True)
    setting_get = setting_sub.add_parser("get")
    setting_get.add_argument("name")
    setting_set = setting_sub.add_parser("set")
    setting_set.add_argument("name")
    setting_set.add_argument("assignments", nargs="+")

    control = sub.add_parser("controls", help="Manage normalized game-control profiles")
    control_sub = control.add_subparsers(dest="controls_command", required=True)
    control_sub.add_parser("list")
    control_import = control_sub.add_parser("import")
    control_import.add_argument("path", type=Path)

    library_parser = sub.add_parser("library", help="Manage the local personal app catalog")
    library_sub = library_parser.add_subparsers(dest="library_command", required=True)
    library_sub.add_parser("list")
    library_add = library_sub.add_parser("add")
    library_add.add_argument("package")
    library_add.add_argument("--title", required=True)
    library_add.add_argument("--cover")
    library_add.add_argument("--favorite", action="store_true")
    library_add.add_argument("--controls")
    library_remove = library_sub.add_parser("remove")
    library_remove.add_argument("package")

    disk = sub.add_parser("disk", help="Report or clean managed cache and snapshots")
    disk_sub = disk.add_subparsers(dest="disk_command", required=True)
    disk_sub.add_parser("report")
    disk_clean = disk_sub.add_parser("clean")
    disk_clean.add_argument("--yes", action="store_true")

    engine_parser = sub.add_parser("engine", help="Inspect the pinned open-source engine")
    engine_parser.add_argument("engine_command", choices=("status",), default="status", nargs="?")

    media_parser = sub.add_parser("media", help="Import or export emulator media")
    _add_serial(media_parser)
    media_sub = media_parser.add_subparsers(dest="media_command", required=True)
    media_import = media_sub.add_parser("import")
    media_import.add_argument("path", type=Path)
    media_export = media_sub.add_parser("export")
    media_export.add_argument("remote")
    media_export.add_argument("destination", type=Path)

    capture_parser = sub.add_parser("capture", help="Capture a PNG screenshot")
    _add_serial(capture_parser)
    capture_parser.add_argument("destination", type=Path)

    record_parser = sub.add_parser("record", help="Record the emulator display to MP4")
    _add_serial(record_parser)
    record_parser.add_argument("destination", type=Path)
    record_parser.add_argument("--seconds", type=int, default=30)

    agent_parser = sub.add_parser("agent", help="Execute one guarded Android automation action")
    _add_serial(agent_parser)
    agent_parser.add_argument("action", choices=sorted(agent.ALLOWED_ACTIONS))
    agent_parser.add_argument("--arguments", default="{}", help="JSON object containing action arguments")
    agent_parser.add_argument("--description", default="")
    agent_parser.add_argument("--yes", action="store_true")

    macro_parser = sub.add_parser("macro", help="Import and replay guarded automation macros")
    _add_serial(macro_parser)
    macro_sub = macro_parser.add_subparsers(dest="macro_command", required=True)
    macro_sub.add_parser("list")
    macro_import = macro_sub.add_parser("import")
    macro_import.add_argument("path", type=Path)
    macro_run = macro_sub.add_parser("run")
    macro_run.add_argument("name")
    macro_run.add_argument("--yes", action="store_true")

    return parser


def _toolchain():
    return discover_toolchain(require_all=True)



def command_main(args: argparse.Namespace) -> int:
    if args.command == "settings":
        if args.settings_command == "get":
            print(json.dumps(settings.get(args.name), sort_keys=True))
        else:
            changes = dict(settings.parse_assignment(item) for item in args.assignments)
            print(json.dumps(settings.update(args.name, changes), sort_keys=True))
        return 0
    if args.command == "instance" and args.instance_command == "update":
        changes = dict(settings.parse_assignment(item) for item in args.assignments)
        print(json.dumps(settings.update(args.name, changes), sort_keys=True))
        return 0
    if args.command == "controls":
        data = controls.list_profiles() if args.controls_command == "list" else controls.import_profile(args.path)
        print(json.dumps(data, sort_keys=True))
        return 0
    if args.command == "macro" and args.macro_command in {"list", "import"}:
        data = macros.list_macros() if args.macro_command == "list" else macros.import_macro(args.path)
        print(json.dumps(data, sort_keys=True))
        return 0
    if args.command == "library":
        if args.library_command == "list":
            data = library.list_apps()
        elif args.library_command == "add":
            data = library.add(args.package, args.title, cover=args.cover, favorite=args.favorite, control_profile=args.controls)
        else:
            data = library.remove(args.package)
        print(json.dumps(data, sort_keys=True))
        return 0
    if args.command == "disk":
        if args.disk_command == "report":
            print(json.dumps(maintenance.disk_report(), sort_keys=True))
            return 0
    if args.command == "engine":
        print(json.dumps(engine.status(), sort_keys=True))
        return 0
    if args.command == "doctor":
        return 0 if print_doctor() else 1

    toolchain = _toolchain()

    if args.command == "disk":
        running_names = {
            adb_module.emulator_avd_name(toolchain, device.serial)
            for device in adb_module.list_devices(toolchain)
            if device.state == "device" and device.serial.startswith("emulator-")
        }
        print(json.dumps(maintenance.clean(confirmed=args.yes, running_names=running_names), sort_keys=True))
        return 0

    if args.command == "update-sdk":
        install_base_packages(toolchain)
        return 0
    if args.command == "images":
        for package in sorted(
            package
            for package in list_packages(toolchain)
            if package.startswith("system-images;") and package.endswith(";arm64-v8a")
        ):
            print(package)
        return 0
    if args.command == "list":
        print("AVDs:")
        for name in avd.list_avds(toolchain):
            print(f"  {name}")
        print("Connected devices:")
        for device in adb_module.list_devices(toolchain):
            print(f"  {device.serial:<16} {device.state:<12} {device.details}")
        return 0
    if args.command == "instance":
        if args.instance_command == "list":
            print(json.dumps({"avds": avd.list_avds(toolchain)}, sort_keys=True))
        elif args.instance_command == "clone":
            print(json.dumps(avd.clone_avd(toolchain, args.source, args.name), sort_keys=True))
        elif args.instance_command == "rename":
            print(json.dumps(avd.rename_avd(toolchain, args.source, args.name), sort_keys=True))
        elif args.instance_command == "delete":
            avd.delete_avd(toolchain, args.name)
            print(json.dumps({"deleted": args.name}, sort_keys=True))
        else:
            started = [
                avd.start_avd(
                    toolchain,
                    name=name,
                    headless=args.headless,
                    wait=True,
                    timeout_seconds=args.timeout,
                    announce=False,
                )
                for name in args.names
            ]
            print(json.dumps({"started": started}, sort_keys=True))
        return 0
    if args.command == "snapshot":
        serial = adb_module.select_device(toolchain, args.serial).serial
        print(avd.snapshot(toolchain, serial, args.operation, args.name))
        return 0
    if args.command == "create":
        metadata = avd.create_avd(
            toolchain,
            name=args.name,
            profile=args.profile,
            api=args.api,
            arch=args.arch,
            device=args.device,
            ram_mb=args.ram_mb,
            data_gb=args.data_gb,
            force=args.force,
        )
        print(json.dumps(metadata, indent=2, sort_keys=True))
        return 0
    if args.command == "start":
        avd.start_avd(
            toolchain,
            name=args.name,
            cold=args.cold,
            wipe=args.wipe,
            headless=args.headless,
            no_audio=args.no_audio,
            wifi_ssid=args.wifi_ssid,
            wifi_password=args.wifi_password,
            dns_servers=args.dns,
            proxy=args.proxy,
            wait=not args.no_wait,
            timeout_seconds=args.timeout,
            extra_args=args.emulator_arg,
        )
        return 0
    if args.command == "stop":
        serial = adb_module.select_device(toolchain, args.serial).serial
        avd.stop_device(toolchain, serial)
        return 0
    if args.command == "delete":
        avd.delete_avd(toolchain, args.name)
        return 0
    if args.command == "identity":
        serial = adb_module.select_device(toolchain, args.serial).serial
        adb_module.print_identity(toolchain, serial, as_json=args.identity_json)
        return 0
    if args.command == "new-identity":
        metadata = avd.create_fresh_identity(toolchain, args.source, args.name)
        print(json.dumps(metadata, indent=2, sort_keys=True))
        return 0
    if args.command == "factory-reset":
        if not args.yes:
            raise AndroidSimError(
                "Factory reset deletes every app, account, and setting in the AVD. Re-run with --yes."
            )
        avd.reset_identity(toolchain, args.name, wait=not args.no_wait)
        return 0
    if args.command == "install":
        serial = adb_module.select_device(toolchain, args.serial).serial
        apps.install_local(
            toolchain,
            serial,
            args.paths,
            replace=not args.no_replace,
            grant=not args.no_grant,
            test_only=args.test_only,
        )
        return 0
    if args.command == "install-url":
        serial = adb_module.select_device(toolchain, args.serial).serial
        apps.install_url(
            toolchain,
            serial,
            args.url,
            sha256=args.sha256,
            allow_http=args.allow_http,
            replace=not args.no_replace,
            grant=not args.no_grant,
            test_only=args.test_only,
        )
        return 0
    if args.command == "download":
        serial = adb_module.select_device(toolchain, args.serial).serial
        remote = apps.push_download(
            toolchain,
            serial,
            args.url,
            sha256=args.sha256,
            allow_http=args.allow_http,
            filename=args.filename,
        )
        print(remote)
        return 0
    if args.command == "play":
        serial = adb_module.select_device(toolchain, args.serial).serial
        apps.open_play_store(toolchain, serial, args.package)
        library.touch(args.package)
        return 0
    if args.command == "launch":
        serial = adb_module.select_device(toolchain, args.serial).serial
        apps.launch_package(toolchain, serial, args.package)
        library.touch(args.package)
        return 0
    if args.command == "uninstall":
        serial = adb_module.select_device(toolchain, args.serial).serial
        apps.uninstall_package(toolchain, serial, args.package, args.keep_data)
        return 0
    if args.command == "apps":
        serial = adb_module.select_device(toolchain, args.serial).serial
        for package in apps.list_apps(toolchain, serial, third_party=not args.all):
            print(package)
        return 0
    if args.command == "shell":
        serial = adb_module.select_device(toolchain, args.serial).serial
        shell_args = list(args.args)
        if shell_args and shell_args[0] == "--":
            shell_args.pop(0)
        if not shell_args:
            raise AndroidSimError("Provide a shell command after '--', for example: android-sim shell -- getprop")
        result = adb_module.adb(toolchain, serial, ["shell", *shell_args], capture=False)
        return result.returncode
    if args.command == "network":
        serial = adb_module.select_device(toolchain, args.serial).serial
        if args.network_command == "status":
            for key, value in network.status(toolchain, serial).items():
                print(f"{key}: {value}")
        elif args.network_command == "wifi":
            network.wifi(toolchain, serial, args.state == "on")
        elif args.network_command == "speed":
            network.set_speed(toolchain, serial, args.preset)
        elif args.network_command == "delay":
            network.set_delay(toolchain, serial, args.preset)
        elif args.network_command == "proxy":
            if args.value == "clear":
                network.clear_proxy(toolchain, serial)
            else:
                network.set_proxy(toolchain, serial, args.value)
        return 0
    if args.command == "media":
        serial = adb_module.select_device(toolchain, args.serial).serial
        data = media.import_file(toolchain, serial, args.path) if args.media_command == "import" else media.export_file(toolchain, serial, args.remote, args.destination)
        print(json.dumps(data, sort_keys=True))
        return 0
    if args.command == "capture":
        serial = adb_module.select_device(toolchain, args.serial).serial
        print(json.dumps(media.capture(toolchain, serial, args.destination), sort_keys=True))
        return 0
    if args.command == "record":
        serial = adb_module.select_device(toolchain, args.serial).serial
        print(json.dumps(media.record(toolchain, serial, args.destination, args.seconds), sort_keys=True))
        return 0
    if args.command == "agent":
        try:
            arguments = json.loads(args.arguments)
        except json.JSONDecodeError as exc:
            raise AndroidSimError(f"Invalid --arguments JSON: {exc}") from exc
        if not isinstance(arguments, dict):
            raise AndroidSimError("--arguments must decode to a JSON object")
        serial = adb_module.select_device(toolchain, args.serial).serial
        action = agent.Action(args.action, arguments, args.description)
        print(json.dumps(agent.execute(toolchain, serial, action, confirmed=args.yes), sort_keys=True))
        return 0
    if args.command == "macro":
        serial = adb_module.select_device(toolchain, args.serial).serial
        print(json.dumps(macros.run_macro(toolchain, serial, args.name, confirmed=args.yes), sort_keys=True))
        return 0

    raise AndroidSimError(f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not args.json_output:
            return command_main(args)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), machine_output():
            code = command_main(args)
        raw = captured.getvalue().strip()
        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            data = {"output": raw}
        emit(Response(status="ok" if code == 0 else "error", data=data, error=None if code == 0 else {"code": "command_failed", "message": f"Command exited with status {code}"}))
        return code
    except AndroidSimError as exc:
        if args.json_output:
            emit(Response(status="error", error={"code": "android_sim_error", "message": str(exc)}))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        if args.json_output:
            emit(Response(status="error", error={"code": "interrupted", "message": "Interrupted by user"}))
        else:
            print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
