#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "error: this build must run on an Apple Silicon Mac" >&2
  exit 2
fi

available_kib=$(df -Pk "${TMPDIR:-/tmp}" | awk 'NR==2 {print $4}')
if [[ "${available_kib:-0}" -lt 83886080 ]]; then
  echo "error: at least 80 GiB free space is required for the engine build" >&2
  exit 2
fi

if ! command -v repo >/dev/null 2>&1; then
  echo "error: Google's repo tool is required; install it before running this build" >&2
  exit 2
fi
if ! xcode-select -p >/dev/null 2>&1; then
  echo "error: Xcode command-line tools are required" >&2
  exit 2
fi

root="${TEMPERA_ENGINE_BUILD_ROOT:-$PWD/.engine-build}"
aosp="$root/emu-master-dev"
engines="${TEMPERA_ENGINE_INSTALL_ROOT:-$HOME/.android-simulator/engines}"
version="aemu-ae9d18d2b626"
destination="$engines/$version"
mkdir -p "$aosp" "$engines"

if [[ ! -d "$aosp/.repo" ]]; then
  (cd "$aosp" && repo init -u https://android.googlesource.com/platform/manifest -b emu-master-dev)
fi
(cd "$aosp" && repo sync -j8 --no-tags --optimized-fetch --prune)

git -C "$aosp/external/qemu" fetch --depth=1 origin ae9d18d2b6261179fbd57fffec720a04f7bfb053
git -C "$aosp/external/qemu" checkout --detach ae9d18d2b6261179fbd57fffec720a04f7bfb053
git -C "$aosp/hardware/google/gfxstream" fetch --depth=1 https://github.com/google/gfxstream.git 5960b81c137b15f74b132fa6b95f5cb326002807
git -C "$aosp/hardware/google/gfxstream" checkout --detach 5960b81c137b15f74b132fa6b95f5cb326002807
git -C "$aosp/external/moltenvk" fetch --depth=1 https://github.com/KhronosGroup/MoltenVK.git 5189f8de86ec365860f63bf1da736815cfaea5cd
git -C "$aosp/external/moltenvk" checkout --detach 5189f8de86ec365860f63bf1da736815cfaea5cd

(cd "$aosp/external/qemu" && ./android/rebuild.sh --gfxstream)
distribution="$aosp/external/qemu/objs/distribution/emulator"
if [[ ! -x "$distribution/emulator" ]]; then
  echo "error: build completed without the expected emulator distribution" >&2
  exit 2
fi
if [[ -e "$destination" ]]; then
  echo "error: versioned destination already exists: $destination" >&2
  exit 2
fi
if [[ -e "$engines/current" && ! -L "$engines/current" ]]; then
  echo "error: refusing to replace non-symlink engine/current" >&2
  exit 2
fi
cp -R "$distribution" "$destination"
ln -sfn "$version" "$engines/current.next"
mv -f "$engines/current.next" "$engines/current"
echo "Installed pinned engine at $destination"
