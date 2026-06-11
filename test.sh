#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Missing virtualenv Python at ${VENV_PYTHON}"
  echo "Create it with: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt"
  exit 1
fi

cd "${ROOT_DIR}"

echo "Running test suite with coverage..."
"${VENV_PYTHON}" -m coverage erase
"${VENV_PYTHON}" -m coverage run -m pytest
"${VENV_PYTHON}" -m coverage html
"${VENV_PYTHON}" -m coverage report

echo
echo "HTML coverage report: ${ROOT_DIR}/htmlcov/index.html"
