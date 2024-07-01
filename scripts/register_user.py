#!/usr/bin/env python3

import argparse
import asyncio
import os
import random
import string
import sys

from taguette import database
from taguette import validate


PASSWORD_CHARS = string.ascii_letters + string.digits + '#%&-.?~'
PASSWORD_LENGTH = 14


async def main():
    parser = argparse.ArgumentParser(
        description="Register a new user",
    )
    parser.add_argument('config_file', help="Configuration file")
    parser.add_argument('login')
    parser.add_argument(
        '--email',
        help="User's email address (optional)",
        action='store',
    )

    args = parser.parse_args()

    config = {}
    config_file = os.path.abspath(args.config_file)
    with open(config_file) as fp:
        code = compile(fp.read(), config_file, 'exec')
    exec(code, config)

    DBSession = database.connect(config['DATABASE'])
    db = DBSession()

    user = db.query(database.User).get(args.login)
    if user is not None:
        print("User exists: %s" % args.login, file=sys.stderr)
        sys.exit(1)

    # Validate input
    login = validate.fix_user_login(args.login, new=True)
    if args.email:
        email = validate.fix_user_email(args.email)
    else:
        email = None
    print("email: %r" % email)

    # Generate password
    password = ''.join(random.choices(PASSWORD_CHARS, k=PASSWORD_LENGTH))

    # Create user
    user = database.User(
        login=login,
        email=email,
    )
    await user.set_password(password)
    db.add(user)
    db.commit()

    print(
        (
            "New user created:\n    login: {login}\n"
            + "    password: {password}"
        ).format(login=login, password=password)
    )


if __name__ == '__main__':
    asyncio.run(main())
