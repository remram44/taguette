#!/bin/bash

set -eux

if [ "x${1:-}" = x ]; then
    echo "Missing version number" >&2
    exit 1
fi
VERSION="$1"

cd "$(dirname "$0")/../.."
cp scripts/dist/pyinstaller_entrypoint.py scripts/dist/macos/macos.spec .
poetry install
scripts/update_translations.sh
rm -rf build dist
pyinstaller macos.spec
rm -rf dist/taguette
cp scripts/dist/macos/taguette_console_wrapper dist/Taguette.app/Contents/MacOS/
cp -a /Applications/calibre.app dist/Taguette.app/Contents/Resources/
(cd dist/Taguette.app/Contents && patch -p0 <../../../scripts/dist/macos/plist.patch)
codesign --deep --force -s Taguette dist/Taguette.app
rm -f taguette.dmg
cp scripts/dist/LICENSE.txt dist/LICENSE.txt
ln -s /Applications dist/Applications
sleep 1
hdiutil create taguette.dmg -srcfolder dist -volname "Taguette $VERSION"
