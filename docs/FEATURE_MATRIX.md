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
| BYOK AI action safety gate | foundation | Guarded action executor; provider planner not bundled |
| SwiftUI manager | foundation | Thin JSON/NDJSON CLI consumer |
| gfxstream + MoltenVK engine | engine-blocked | Source pins and Mac build preflight supplied |
| Vulkan, V-Sync, Retina and 240 FPS validation | evidence-needed | Must be tested on Apple Silicon hardware |
| BlueStacks package internals | foundation | Official 5.21.790.7505 PKG acquired, hashed and statically inventoried; macOS runtime evidence remains open |
| Macro import/replay and cross-instance input sync | foundation | Guarded versioned macro replay implemented; live recording and cross-instance fan-out require macOS input bridge |
| Backup/restore, eco FPS and instance arrangement | evidence-needed | Feature surface observed in shipped binary; clean-room implementation pending |
| Prime, NowBux, rewards, ads and BlueStacks assets | excluded | Commercial/brand services |
| Device/attestation spoofing and anti-cheat bypass | excluded | Security boundary |
