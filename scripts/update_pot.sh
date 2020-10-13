#!/bin/sh

set -eu

cd "$(dirname "$(dirname "$0")")"
pybabel extract -F scripts/babelrc -k _f -c TRANSLATORS: -s -o po/website.pot *.html
