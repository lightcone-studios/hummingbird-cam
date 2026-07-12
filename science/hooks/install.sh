#!/usr/bin/env bash
# Install the science pre-commit gate into this clone. Run once per clone.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cp "$ROOT/science/hooks/pre-commit" "$ROOT/.git/hooks/pre-commit"
chmod +x "$ROOT/.git/hooks/pre-commit"
echo "installed: .git/hooks/pre-commit -> runs science.py check on every commit"
