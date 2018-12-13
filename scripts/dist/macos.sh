#!/bin/bash

set -eux

if [ "x${1:-}" = x ]; then
    echo "Missing version number" >&2
    exit 1
fi
VERSION="$1"

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
cp scripts/dist/LICENSE.txt dist/LICENSE.txt
ln -s /Applications dist/Applications
sleep 1
#hdiutil create taguette.dmg -srcfolder dist -volname "Taguette $VERSION"
EMPTYDIR="$(mktemp -d /tmp/emptydir.XXXXXX)"
rm -f taguette.dmg
../create-dmg/create-dmg --volname "Taguette $VERSION" --icon-size 64 --background scripts/dist/macos/dmg-background.png --window-size 480 350 --add-file LICENSE.txt scripts/dist/LICENSE.txt 113 67 --app-drop-link 111 228 --add-folder Taguette.app dist/Taguette.app 355 220 taguette.dmg "$EMPTYDIR"
rmdir "$EMPTYDIR"
