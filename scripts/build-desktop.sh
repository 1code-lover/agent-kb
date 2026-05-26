#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--install-deps" ]]; then
  python3 -m pip install -r "$ROOT/requirements.txt"
  (cd "$ROOT/webapp" && npm install && npm run build)
  (cd "$ROOT/desktop" && npm install)
fi

cd "$ROOT/desktop"
npm run build
