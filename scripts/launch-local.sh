#!/usr/bin/env bash
# Bootstraps a venv with a working tkinter and launches the desktop app.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

VENV=.venv
PY=python3.12

if ! command -v $PY >/dev/null 2>&1; then
  echo "error: $PY not found. Install it (e.g. 'brew install python@3.12')." >&2
  exit 1
fi

if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c "import tkinter" >/dev/null 2>&1; then
  echo "Setting up venv with tkinter support..."
  if ! $PY -c "import tkinter" >/dev/null 2>&1; then
    if [[ "$OSTYPE" == darwin* ]] && command -v brew >/dev/null 2>&1; then
      brew install python-tk@3.12
    else
      echo "error: $PY has no tkinter. Install the matching tk package for your platform." >&2
      exit 1
    fi
  fi
  rm -rf "$VENV"
  $PY -m venv "$VENV"
fi

"$VENV/bin/pip" install -q -r requirements.txt
exec "$VENV/bin/python" app.py
