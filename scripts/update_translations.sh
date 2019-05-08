#!/bin/sh

cd "$(dirname "$(dirname "$0")")"
pybabel extract -F scripts/babelrc -o po/taguette.pot $(find taguette -name '*.py' -o -name '*.js' -o -name '*.html')
for i in po/*.mo; do
    DIR=taguette/l10n/$(echo $i | sed 's/^po\///' | sed 's/\.mo$//')/LC_MESSAGES
    mkdir -p $DIR
    cp $i $DIR/taguette.mo
done
