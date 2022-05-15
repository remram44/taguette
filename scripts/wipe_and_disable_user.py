#!/usr/bin/env python3

import argparse
import os
import sys
import time
from tornado.web import create_signed_value

from taguette import database


def main():
    parser = argparse.ArgumentParser(
        description="Wipe user data and disable it",
    )
    parser.add_argument('config_file', help="Configuration file")
    parser.add_argument('user_login')

    args = parser.parse_args()

    config = {}
    config_file = os.path.abspath(args.config_file)
    with open(config_file) as fp:
        code = compile(fp.read(), config_file, 'exec')
    exec(code, config)

    DBSession = database.connect(config['DATABASE'])
    db = DBSession()

    user = db.query(database.User).get(args.user_login)
    if user is None:
        print("No such user: %r" % args.user_login, file=sys.stderr)
        sys.exit(1)

    if user.disabled:
        print("User is already disabled")
        sys.exit(3)

    if user.projects:
        print("User has projects")
        sys.exit(1)

    user.hashed_password = ''
    user.language = None
    user.email = None
    user.disabled = True
    db.commit()


if __name__ == '__main__':
    main()
