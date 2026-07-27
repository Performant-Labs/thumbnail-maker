#!/usr/bin/env bash
# Build the macOS .app.  Run on macOS:  ./build_macos.sh
set -euo pipefail

python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --clean --noconfirm ThumbnailMaker.spec

echo ""
echo "Built: dist/Thumbnail Maker.app"
echo ""
echo "First launch is blocked by Gatekeeper because the app is unsigned."
echo "Either right-click the app > Open (once), or run:"
echo "  xattr -dr com.apple.quarantine 'dist/Thumbnail Maker.app'"
