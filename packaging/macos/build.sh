#!/bin/sh
# Build dist/SlidePrint.app and dist/SlidePrint.dmg locally in a clean virtual environment
# (on macOS; needs Python 3.12: python3.12 on PATH, or PYTHON=/path/to/python3 packaging/macos/build.sh).
set -e
cd "$(dirname "$0")/../.."
trap '[ $? -eq 0 ] || echo "Build failed."' EXIT
# Icon set to ship: a folder in icons/ (cards or layers); see icons/make_assets.py
export ICONSET=layers
# Stop, rather than make an app that macOS says is damaged, if signing it (ad hoc) goes wrong
export PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR=1 PYINSTALLER_VERIFY_BUNDLE_SIGNATURE=1
[ -d .venv ] || "${PYTHON:-python3.12}" -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt -r requirements-build.txt
.venv/bin/python tests/test_dedup.py
.venv/bin/python -m PyInstaller --noconfirm packaging/macos/SlidePrint.spec
# Disk image: the app, and a link to drag it onto Applications
rm -rf build/dmg dist/SlidePrint.dmg
mkdir -p build/dmg
ditto dist/SlidePrint.app build/dmg/SlidePrint.app
ln -s /Applications build/dmg/Applications
hdiutil create -quiet -volname SlidePrint -srcfolder build/dmg -fs HFS+ -format UDZO dist/SlidePrint.dmg
echo
echo "Built dist/SlidePrint.app and dist/SlidePrint.dmg"
