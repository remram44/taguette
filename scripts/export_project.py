#!/usr/bin/env python3

import argparse
from taguette import database


def copy_projects(source, destination, projects):
    source = database.connect(source)()
    destination = database.connect(destination)()

    for project_id in projects:
        # Copy Project (id, name, description, created)
        # Copy User (login)
        # Copy ProjectMember (project_id, user_login, privileges)
        # Copy Document (id, name, description, filename, created, project_id, contents)
        # Copy Group (id, project_id, path, description)
        # Copy DocumentGroup (document_id, group_id)
        # Copy Highlight (id, document_id, start_offset, end_offset, snippet)
        # Copy Tag (id, project_id, path, description)
        # Copy HighlightTag (highlight_id, tag_id)
        # Copy Command (id, date, user_login, project_id, document_id, payload)
        TODO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', help="Source database URI")
    parser.add_argument('destination', help="Destination database URI")
    parser.add_argument('project', help="Project ID",
                        nargs=argparse.ONE_OR_MORE)

    args = parser.parse_args()

    copy_projects(args.source, args.destination, args.project)


if __name__ == '__main__':
    main()
