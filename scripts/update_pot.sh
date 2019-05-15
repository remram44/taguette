#!/bin/sh

set -eu

cd "$(dirname "$(dirname "$0")")"
pybabel extract -F scripts/babelrc -c TRANSLATORS: -s -o po/main.pot $(find taguette -name '*.py' -o -name '*.html')
pybabel extract -F scripts/babelrc -c TRANSLATORS: -s -o po/javascript.pot $(find taguette -name '*.js')
