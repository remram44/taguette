#!/usr/bin/env python3

import argparse
import os
import sys
import time
from tornado.web import create_signed_value

from taguette import database


def main():
    parser = argparse.ArgumentParser(
        description="Generate a password reset link for manual delivery",
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
        print("WARNING: USER IS DISABLED")

    # Generate a signed token
    reset_token = '%s|%s|%s' % (
        int(time.time()),
        user.login,
        user.email,
    )
    reset_token = create_signed_value(
        config['SECRET_KEY'],
        'reset_token',
        reset_token,
    )
    reset_token = reset_token.decode('utf-8')
    reset_link = '/new_password?reset_token=' + reset_token

    print(reset_link)


if __name__ == '__main__':
    main()
