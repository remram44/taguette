#!/bin/sh

set -eu

cd "$(dirname "$(dirname "$0")")"
find po -name 'main_*.po' | while read fin; do
    loc=$(echo $fin | sed 's/^po\/main_//' | sed 's/\.po$//')
    dir=taguette/l10n/$loc/LC_MESSAGES
    mkdir -p $dir
    pybabel compile -i $fin -o $dir/taguette_main.mo
done
find po -name 'javascript_*.po' | while read fin; do
    loc=$(echo $fin | sed 's/^po\/javascript_//' | sed 's/\.po$//')
    dir=taguette/l10n/$loc/LC_MESSAGES
    mkdir -p $dir
    pybabel compile -i $fin -o $dir/taguette_javascript.mo
done
