# Tempera Air feature matrix

Status values are `implemented`, `foundation`, `engine-blocked`, `evidence-needed`, or `excluded`.

| Capability | Status | Evidence / implementation |
| --- | --- | --- |
| Persistent Apple Silicon AVDs and Play/AOSP profiles | implemented | Upstream Tempera behavior and tests |
| Stable JSON envelope | implemented | `android-sim --json ...` schema v1 |
| Per-instance CPU/RAM/display/DPI/FPS/renderer settings | implemented | Validated metadata with restart reporting |
| Instance clone/rename/update/delete/batch start | implemented | Stopped-instance filesystem operations and validated settings |
| Snapshot commands | implemented | Android emulator console bridge |
| Local personal app catalog | implemented | Versioned local manifest; no commercial backend |
| Normalized control-profile import/list | implemented | Schema v1 validation |
| Low-latency control injection and overlay | foundation | Requires macOS gRPC/GameController client |
| Media import/export and screenshots | implemented | ADB-backed operations |
| Microphone/camera controls | foundation | Settings and permission UX require macOS verification |
| Disk report and cleanup | implemented | Managed roots only, explicit confirmation |
| BYOK AI action safety gate | implemented | User-registered HTTPS planner profiles with env-held keys; plans are validated against the macro contract and replayed only through the existing confirmation gates (`docs/PLANNER_CONTRACT.md`) |
| SwiftUI manager | foundation | Thin JSON/NDJSON CLI consumer |
| Reproducible AEMU engine source/build pipeline | implemented | 76-project frozen manifest, compatible gfxstream pin, MoltenVK build, receipts and atomic install |
| Built gfxstream + MoltenVK engine binary | evidence-needed | Manual Apple Silicon build workflow supplied; binary has not been produced on this Windows host |
| Vulkan, V-Sync, Retina and 240 FPS validation | evidence-needed | Must be tested on Apple Silicon hardware |
| BlueStacks package internals | foundation | Official 5.21.790.7505 PKG acquired, hashed and statically inventoried; macOS runtime evidence remains open |
| Macro import/replay and cross-instance input sync | implemented | Guarded macro replay, action-level recording sessions, and multi-instance fan-out with per-target error reporting; raw touch-stream capture still requires the macOS input bridge |
| Backup/restore, eco FPS and instance arrangement | implemented | Full stopped-instance backup/restore with manifest size verification; per-instance `eco_mode` caps launch FPS at 30; grid planner persists window offsets applied on next start (live window placement pending macOS verification) |
| Prime, NowBux, rewards, ads and BlueStacks assets | excluded | Commercial/brand services |
| Device/attestation spoofing and anti-cheat bypass | excluded | Security boundary |
