# BlueStacks Air clean-room evidence ledger

## Analyzed artifact

- Product: BlueStacks Air 5.21.790.7505.
- Official download API: `https://cloud.bluestacks.com/api/getdownloadnow?platform=mac`.
- Downloaded PKG SHA-256:
  `137accd707aa21028abf57412820d803fe550b07a1d5110ada291b80e10877aa`.
- REA confirmed the artifact as a PKG and bound the same digest. Summary
  Evidence: `ev_7a9617192f1492281e5c8f2dcb0085d76b36d7d390fcb67c210158705ac6186c`.
- REA's Windows artifact provider can attest the PKG root but requires native
  macOS tooling for child inventory, plist/signature inspection, and Mach-O
  analysis. The payload was therefore extracted without execution using
  bsdtar after verifying all 2,523 paths were relative and traversal-free.
- macOS runtime behavior remains unknown until manual acceptance is run on
  Apple Silicon. Static strings and package layout are not runtime proof.

The reproducible source, digest, extraction counts, and REA IDs are stored in
`evidence/bluestacks-air/manifest.json`. Large proprietary package bytes and
the extracted application are deliberately git-ignored. The three retained REA
records are exported to `evidence/bluestacks-air/rea-evidence.json` for replay.

## Publicly documented baseline

These sources define requirements, not reverse-engineered implementation facts:

- BlueStacks Air settings: CPU/RAM, resolution/DPI, renderer, FPS display.
  <https://support.bluestacks.com/hc/en-us/articles/32272893259533>
- Multi-instance creation and cloning.
  <https://support.bluestacks.com/hc/en-us/articles/34711762593037>
- Keyboard/trackpad control overlay.
  <https://support.bluestacks.com/hc/en-us/articles/32337810945293>
- Media transfer and microphone behavior.
  <https://support.bluestacks.com/hc/en-us/articles/33603404995725>
  <https://support.bluestacks.com/hc/en-us/articles/33605457956237>
- Current release notes, including high FPS, V-Sync, device profiles, camera,
  multi-monitor behavior, and BlueAI.
  <https://support.bluestacks.com/hc/en-us/articles/32646860057357>

| Question | Classification | Evidence ID | Result |
| --- | --- | --- | --- |
| Package identity | observed | `ev_7a9617…` | Official PKG 5.21.790.7505, arm64-only installer declaration |
| Bundle roots and helpers | observed-static | local payload inventory | Main app, separate multi-instance manager, QtWebEngine helper, BlueStacks AI Runtime helper |
| Virtualization/storage | observed-static | local payload inventory | `qemu-system-aarch64`, HVF kernel, EDK2 firmware, `Root.qcow2`, `data-org.qcow2` |
| Renderer/framework dependencies | observed-static | local payload inventory | MoltenVK ICD/library, Metal and GameController references, OpenGL renderer and GLES libraries |
| Control-profile resources | observed-static | local payload inventory | Versioned JSON control scheme with native-cursor mapping; proprietary profile content is not copied |
| Feature surface | observed-static | main executable byte scan | VSync/FPS, Vulkan, clone/fresh instance, screen recording, media, camera/mic, gamepad, location, macros, sync, trim-memory and BlueAI labels/symbols |
| Instance storage layout after installation | unknown | — | Requires macOS runtime observation |
| Signing and entitlements | partial | local plist parse | Camera/microphone usage strings observed; signature verification requires macOS |
| Runtime behavior and performance | unknown | — | Requires Apple Silicon controlled scenarios |
