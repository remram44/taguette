#!/usr/bin/env python3

import argparse
import logging
import os
import pkg_resources
from sqlalchemy.orm.exc import ObjectDeletedError
import sys
import tornado.locale

from taguette import database, validate, convert


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Run validation on an existing database",
    )
    parser.add_argument('config_file', help="Configuration file")
    parser.add_argument('--users', action='store_true',
                        help="Validate users")
    parser.add_argument('--projects', action='store_true',
                        help="Validate project metadata")
    parser.add_argument('--documents', action='store_true',
                        help="Validate documents")
    parser.add_argument('--tags', action='store_true',
                        help="Validate tags")
    parser.add_argument('--export', action='store_true',
                        help="Try to export all projects")

    args = parser.parse_args()

    config = {}
    config_file = os.path.abspath(args.config_file)
    with open(config_file) as fp:
        code = compile(fp.read(), config_file, 'exec')
    exec(code, config)

    DBSession = database.connect(config['DATABASE'])
    db = DBSession()

    errors = 0

    def check(func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except validate.InvalidFormat:
            return False

    if args.users:
        d = pkg_resources.resource_filename('taguette', 'l10n')
        tornado.locale.load_gettext_translations(d, 'taguette_main')

        for user in db.query(database.User):
            if not check(validate.user_login, user.login):
                errors += 1
                print("Invalid user login: %r" % user.login)
            if user.email and not check(validate.user_email, user.email):
                errors += 1
                print("Invalid user email for %r: %r" % (
                    user.login,
                    user.email,
                ))
            if (
                user.language
                and user.language not in tornado.locale.get_supported_locales()
            ):
                errors += 1
                print("User locale unsupported for %r: %r" % (
                    user.login,
                    user.language,
                ))

    if args.projects:
        for project in db.query(database.Project):
            if not check(validate.project_name, project.name):
                errors += 1
                print("Invalid project name: %r" % project.name)
            if not check(validate.description, project.description):
                errors += 1
                print("Invalid project description for %d (%r): %r" % (
                    project.id,
                    project.name,
                    project.description,
                ))

    if args.documents:
        for document in db.query(database.Document):
            if not check(validate.document_name, document.name):
                errors += 1
                print("Invalid document name for %r: %r" % (
                    document.id,
                    document.name,
                ))
            if not check(validate.description, document.description):
                errors += 1
                print("Invalid document description for %d (%r): %r" % (
                    document.id,
                    document.name,
                    document.description,
                ))
            if not check(validate.filename, document.filename):
                errors += 1
                print("Invalid document filename for %d (%r): %r" % (
                    document.id,
                    document.name,
                    document.filename,
                ))
            try:
                contents = document.contents
            except ObjectDeletedError:
                # The document was deleted since we started iterating
                pass
            else:
                if not convert.is_html_safe(contents):
                    errors += 1
                    print("Invalid document contents for %d (%r)" % (
                        document.id,
                        document.name,
                    ))

    if args.tags:
        for tag in db.query(database.Tag):
            if not check(validate.tag_path, tag.path):
                errors += 1
                print("Invalid tag path for %d: %r" % (tag.id, tag.path))
            if not check(validate.description, tag.description):
                errors += 1
                print("Invalid tag description for %d (%r): %r" % (
                    tag.id,
                    tag.path,
                    tag.description
                ))

    print("%d errors found" % errors)
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
