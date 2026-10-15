#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "error: run this on the Mac where BlueStacks Air is installed" >&2
  exit 2
fi

source_app="${1:-/Applications/BlueStacks.app}"
destination="${2:-$PWD/BlueStacks-Air-for-REA.zip}"
if [[ ! -d "$source_app" || "$source_app" != *.app ]]; then
  echo "error: app bundle not found: $source_app" >&2
  exit 2
fi
if [[ -e "$destination" ]]; then
  echo "error: destination already exists: $destination" >&2
  exit 2
fi

ditto -c -k --sequesterRsrc --keepParent "$source_app" "$destination"
shasum -a 256 "$destination" | tee "$destination.sha256"
echo "Copy both files into the Tempera Air workspace, then open the ZIP with REA MCP."
