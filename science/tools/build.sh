#!/usr/bin/env bash
# Build the Secure Enclave signer. Shiro-only (needs Apple Silicon + Swift/CryptoKit).
# Ad-hoc code signing is required for the process to reach the enclave; no entitlements needed.
set -euo pipefail
cd "$(dirname "$0")"

command -v swiftc >/dev/null || { echo "build.sh: swiftc not found (this tool builds on macOS only)"; exit 1; }

swiftc -O sesign.swift -o sesign
codesign --sign - --force sesign
echo "built + ad-hoc signed: $(pwd)/sesign"
