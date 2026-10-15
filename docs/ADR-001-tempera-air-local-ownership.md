# ADR-001: Local state and UI ownership

## Decision

`android_simulator` owns all durable local emulator state and state transitions.
The committed `contracts/cli-response.schema.json` envelope plus command handlers
form the public local contract. The SwiftUI application is a thin consumer and
does not write AVD metadata, catalog entries, control profiles, or engine state.

State remains local and single-user. Existing per-instance JSON is migrated
atomically with a one-time v0 backup; a network service and central auth scopes
are intentionally not introduced. Provider API keys belong to macOS Keychain
and are never written to project state.

## Compatibility and rollback

Existing CLI text output stays unchanged unless `--json` is selected. Existing
metadata remains readable. Rollback consists of restoring the `.json.v0.bak`
file and using the upstream SDK emulator; custom engine sources are pinned and
installed outside the repository.

## Maturity

Python behavior is locally tested. SwiftUI, AEMU, gfxstream, MoltenVK, input
latency, Vulkan, microphone, camera, and high-FPS claims remain hardware-gated
until the macOS acceptance bundle is returned.
