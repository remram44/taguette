#!/usr/bin/env python3

import argparse
import os
from sqlalchemy.orm import joinedload
import sys

from taguette import database


def main():
    parser = argparse.ArgumentParser(
        description="Wipe user data and disable it",
    )
    parser.add_argument('config_file', help="Configuration file")
    parser.add_argument('user_login')
    parser.add_argument(
        '--delete-projects',
        action='store_true',
        help="If projects exist, delete them rather than bailing out",
    )

    args = parser.parse_args()

    config = {}
    config_file = os.path.abspath(args.config_file)
    with open(config_file) as fp:
        code = compile(fp.read(), config_file, 'exec')
    exec(code, config)

    DBSession = database.connect(config['DATABASE'])
    db = DBSession()

    user = (
        db.query(database.User)
        .options(
            joinedload(database.User.project_memberships)
            .options(joinedload(database.ProjectMember.project))
        )
        .get(args.user_login)
    )
    if user is None:
        print("No such user: %r" % args.user_login, file=sys.stderr)
        sys.exit(1)

    if user.disabled:
        print("User is already disabled")
        sys.exit(3)

    if not args.delete_projects:
        sole_admin = False

        for membership in user.project_memberships:
            project = membership.project

            # Check if that project has other members
            if not any(
                member.user_login != user.login
                for member in project.members
            ):
                sole_admin = True
                print("User is sole member of project %d %r" % (
                    project.id, project.name,
                ))

        if sole_admin:
            sys.exit(1)

    else:
        for membership in user.project_memberships:
            project = membership.project

            # Check if that project has other members
            if not any(
                member.user_login != user.login
                for member in project.members
            ):
                print("Deleting project %d %r" % (project.id, project.name))
                db.delete(project)

    user.project_memberships.clear()
    user.hashed_password = ''
    user.language = None
    user.email = None
    user.disabled = True
    db.commit()


if __name__ == '__main__':
    main()
