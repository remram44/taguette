#!/bin/sh

set -eu

cd "$(dirname "$(dirname "$0")")"
pybabel extract -F scripts/babelrc -o po/taguette.pot $(find taguette -name '*.py' -o -name '*.js' -o -name '*.html')
find po -name '*.po' | while read fin; do
    loc=$(echo $fin | sed 's/^po\///' | sed 's/\.po$//')
    dir=taguette/l10n/$loc/LC_MESSAGES
    mkdir -p $dir
    pybabel compile -i $fin -o $dir/taguette.mo
done
