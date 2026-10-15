#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
lock="$script_dir/engine.lock.json"
verify_lock="$script_dir/verify-lock.py"
verify_manifest="$script_dir/verify-source-manifest.py"
receipt_tool="$script_dir/build-receipt.py"

read_lock() {
  python3 -c 'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); result=value; [result:=result[key] for key in sys.argv[2].split(".")]; print(result)' "$lock" "$1"
}

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "error: this build must run on an Apple Silicon Mac" >&2
  exit 2
fi

for tool in python3 git shasum xcodebuild clang lipo ditto; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "error: required build tool is missing: $tool" >&2
    exit 2
  fi
done
python3 "$verify_lock"

available_kib=$(df -Pk "${TMPDIR:-/tmp}" | awk 'NR==2 {print $4}')
minimum_free_gib="$(read_lock build.minimum_free_gib)"
minimum_free_kib=$((minimum_free_gib * 1024 * 1024))
if [[ "${available_kib:-0}" -lt "$minimum_free_kib" ]]; then
  echo "error: at least $minimum_free_gib GiB free space is required for the engine build" >&2
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
version="$(read_lock lock_id)"
destination="$engines/$version"
mkdir -p "$aosp" "$engines"

manifest_repository="$(read_lock manifest.repository)"
manifest_commit="$(read_lock manifest.commit)"
frozen_overlay="$script_dir/$(read_lock manifest.frozen_overlay)"
overlay_sha="$(read_lock manifest.frozen_overlay_sha256)"
if [[ "$(shasum -a 256 "$frozen_overlay" | awk '{print $1}')" != "$overlay_sha" ]]; then
  echo "error: frozen source manifest digest does not match engine.lock.json" >&2
  exit 2
fi

(cd "$aosp" && repo init -u "$manifest_repository" -b "$manifest_commit")
mkdir -p "$aosp/.repo/local_manifests"
ditto "$frozen_overlay" "$aosp/.repo/local_manifests/tempera-frozen.xml"
jobs="${TEMPERA_ENGINE_JOBS:-$(sysctl -n hw.logicalcpu)}"
(cd "$aosp" && repo sync -j"$jobs" --no-tags --optimized-fetch --prune --fail-fast)

resolved_manifest="$root/source-manifest.xml"
(cd "$aosp" && repo manifest -r -o "$resolved_manifest")
python3 "$verify_manifest" "$frozen_overlay" "$resolved_manifest"

aemu_commit="$(read_lock components.aemu.commit)"
gfxstream_commit="$(read_lock components.gfxstream.commit)"
if [[ "$(git -C "$aosp/external/qemu" rev-parse HEAD)" != "$aemu_commit" ]]; then
  echo "error: AEMU checkout does not match the locked commit" >&2
  exit 2
fi
if [[ "$(git -C "$aosp/hardware/google/gfxstream" rev-parse HEAD)" != "$gfxstream_commit" ]]; then
  echo "error: gfxstream checkout does not match the compatible locked commit" >&2
  exit 2
fi

moltenvk="$aosp/external/tempera-moltenvk"
moltenvk_repository="$(read_lock components.moltenvk.repository)"
moltenvk_commit="$(read_lock components.moltenvk.commit)"
if [[ ! -d "$moltenvk/.git" ]]; then
  git clone --filter=blob:none --no-checkout "$moltenvk_repository" "$moltenvk"
fi
git -C "$moltenvk" fetch --depth=1 origin "$moltenvk_commit"
git -C "$moltenvk" checkout --detach "$moltenvk_commit"
(cd "$moltenvk" && ./fetchDependencies --macos && make macos)

(cd "$aosp/external/qemu" && ./android/rebuild.sh --gfxstream)
distribution="$aosp/external/qemu/objs/distribution/emulator"
if [[ ! -x "$distribution/emulator" ]]; then
  echo "error: build completed without the expected emulator distribution" >&2
  exit 2
fi
if [[ " $(lipo -archs "$distribution/emulator") " != *" arm64 "* ]]; then
  echo "error: built emulator does not contain an arm64 slice" >&2
  exit 2
fi

moltenvk_dylib="$moltenvk/Package/Latest/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib"
moltenvk_icd="$moltenvk/MoltenVK/icd/MoltenVK_icd.json"
if [[ ! -f "$moltenvk_dylib" || ! -f "$moltenvk_icd" ]]; then
  echo "error: MoltenVK build completed without the expected macOS package" >&2
  exit 2
fi
mkdir -p "$distribution/lib64/vulkan"
ditto "$moltenvk_dylib" "$distribution/lib64/vulkan/libMoltenVK-tempera.dylib"
sed 's#\./libMoltenVK\.dylib#./libMoltenVK-tempera.dylib#g' \
  "$moltenvk_icd" > "$distribution/lib64/vulkan/Tempera_MoltenVK_icd.json"
ditto "$resolved_manifest" "$distribution/source-manifest.xml"
python3 "$receipt_tool" "$lock" "$distribution" "$resolved_manifest" "$distribution/build-receipt.json"

if [[ -e "$destination" ]]; then
  echo "error: versioned destination already exists: $destination" >&2
  exit 2
fi
if [[ -e "$engines/current" && ! -L "$engines/current" ]]; then
  echo "error: refusing to replace non-symlink engine/current" >&2
  exit 2
fi
staging="$engines/.$version.staging.$$"
if [[ -e "$staging" ]]; then
  echo "error: staging destination already exists: $staging" >&2
  exit 2
fi
ditto "$distribution" "$staging"
mv "$staging" "$destination"
ln -sfn "$version" "$engines/current.next"
mv -f "$engines/current.next" "$engines/current"
echo "Installed pinned engine at $destination"
