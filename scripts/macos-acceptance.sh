#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "error: run this on an Apple Silicon Mac" >&2
  exit 2
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="${1:-$PWD/tempera-air-diagnostics-$stamp}"
mkdir -p "$out"

system_profiler SPHardwareDataType SPSoftwareDataType > "$out/system.txt"
android-sim --version > "$out/version.txt"
android-sim --json doctor > "$out/doctor.json" || true
android-sim --json engine status > "$out/engine.json" || true
android-sim --json list > "$out/instances.json" || true
android-sim --json disk report > "$out/disk.json" || true

tar -czf "$out.tar.gz" -C "$(dirname "$out")" "$(basename "$out")"
echo "$out.tar.gz"
