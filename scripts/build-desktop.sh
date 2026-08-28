#!/usr/bin/env bash
# NorthAgent / ThinkRAG local desktop build helper
# - Defaults to the runtime install profile; switch to full only when local OCR / legacy extras are truly needed
# - Prefers KB_PYTHON, then NORTHAGENT/THINKRAG/FOXGLOVE compatibility aliases
# - Reuses the active CONDA_PREFIX / VIRTUAL_ENV before falling back to project-local .venv / venv or PATH python
# - Only builds webapp/dist + the Electron bundle for local verification; it does not replace desktop/package.json build:preflight / release:mac
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DEPS=0
INSTALL_PROFILE="runtime"

resolve_python_cmd() {
  if [[ -n "${KB_PYTHON:-}" ]]; then
    printf '%s\n' "$KB_PYTHON"
    return 0
  fi
  if [[ -n "${NORTHAGENT_PYTHON:-}" ]]; then
    printf '%s\n' "$NORTHAGENT_PYTHON"
    return 0
  fi
  if [[ -n "${THINKRAG_PYTHON:-}" ]]; then
    printf '%s\n' "$THINKRAG_PYTHON"
    return 0
  fi
  if [[ -n "${FOXGLOVE_PYTHON:-}" ]]; then
    printf '%s\n' "$FOXGLOVE_PYTHON"
    return 0
  fi
  if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
    printf '%s\n' "${CONDA_PREFIX}/bin/python"
    return 0
  fi
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    printf '%s\n' "${VIRTUAL_ENV}/bin/python"
    return 0
  fi
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    printf '%s\n' "$ROOT/.venv/bin/python"
    return 0
  fi
  if [[ -x "$ROOT/venv/bin/python" ]]; then
    printf '%s\n' "$ROOT/venv/bin/python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  command -v python
}

resolve_npm_cmd() {
  command -v npm
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-deps)
      INSTALL_DEPS=1
      shift
      ;;
    --install-profile)
      if [[ $# -lt 2 ]]; then
        echo "missing value for --install-profile (expected runtime|full)" >&2
        exit 1
      fi
      INSTALL_PROFILE="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

case "$INSTALL_PROFILE" in
  runtime)
    REQUIREMENTS_FILE="$ROOT/requirements-runtime.txt"
    ;;
  full)
    REQUIREMENTS_FILE="$ROOT/requirements.txt"
    ;;
  *)
    echo "unsupported install profile: $INSTALL_PROFILE (expected runtime|full)" >&2
    exit 1
    ;;
esac

PYTHON_CMD="$(resolve_python_cmd)"
NPM_CMD="$(resolve_npm_cmd)"

if [[ "$INSTALL_DEPS" == "1" ]]; then
  "$PYTHON_CMD" -m pip install -r "$REQUIREMENTS_FILE"
  (cd "$ROOT/webapp" && "$NPM_CMD" install && "$NPM_CMD" run build)
  (cd "$ROOT/desktop" && "$NPM_CMD" install)
fi

cd "$ROOT/desktop"
"$NPM_CMD" run build
