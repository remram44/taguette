#!/bin/bash

if [ "$#" != 1 ]; then
    echo "Usage: new_db_revision.sh \"message\"" >&2
    exit 2
fi

alembic -x db=sqlite:///$HOME/.local/share/taguette/taguette.sqlite3 revision --autogenerate -m "${1}"
