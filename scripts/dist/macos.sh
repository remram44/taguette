#!/bin/bash

set -eux

cd "$(dirname "$0")/../.."
cp scripts/dist/pyinstaller_entrypoint.py scripts/dist/macos/macos.spec .
pip install -e .
rm -rf build dist
pyinstaller macos.spec
rm -rf dist/taguette
cp scripts/dist/macos/taguette_console_wrapper dist/Taguette.app/Contents/MacOS/
cp -a /Applications/calibre.app dist/Taguette.app/Contents/Resources/
(cd dist/Taguette.app/Contents && patch -p0 <../../../scripts/dist/macos/plist.patch)
codesign --deep -s Taguette dist/Taguette.app
rm -f taguette.dmg
hdiutil create taguette.dmg -srcfolder dist
