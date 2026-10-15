# Tempera Air engine build

The engine build is intentionally separate from normal application CI. A full
AEMU checkout and build needs an Apple Silicon Mac, Xcode, Google's `repo` tool,
and at least 80 GiB of free space.

```bash
./engine/build-macos-arm64.sh
```

The build consumes `engine.lock.json` and the checked-in frozen manifest. All
76 AOSP projects are pinned to the revisions from Android superproject commit
`230c45eb81fbc87b94d887073b040ee24139cce9`. The script rejects a source tree
whose resolved manifest differs from those pins.

MoltenVK is built from its separate pinned repository and staged under a unique
filename and ICD manifest. It does not overwrite AEMU's fallback Vulkan files.
Every installed engine contains `source-manifest.xml` and
`build-receipt.json`, including toolchain versions and artifact SHA-256 values.

The manual `engine-macos-arm64` workflow targets a deliberately labelled
self-hosted runner (`macOS`, `ARM64`, `tempera-engine`) because ordinary hosted
macOS runners do not guarantee the disk capacity required by the full build.
