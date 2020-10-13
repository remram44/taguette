#!/bin/sh

set -eu

cd "$(dirname "$(dirname "$0")")"
find po -name 'website_*.po' | while read fin; do
    loc=$(echo $fin | sed 's/^po\/website_//' | sed 's/\.po$//')
    dir=l10n/$loc/LC_MESSAGES
    mkdir -p $dir
    pybabel compile -i $fin -o $dir/taguette_website.mo
done
