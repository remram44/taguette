import codecs
import csv

from .web.base import _f


class InvalidCodebook(ValueError):
    """File can't be read as a codebook.
    """
    def __init__(self, message):
        super(InvalidCodebook, self).__init__(message)
        self.message = message


def list_tags_csv(reader):
    reader = codecs.getreader('utf-8')(reader)
    reader = csv.reader(reader)

    # Read header
    try:
        header = next(reader)
    except (StopIteration, csv.Error, UnicodeDecodeError):
        raise InvalidCodebook(_f("Invalid file: CSV expected"))

    # Figure out which column has the tag path
    expected = ('tag' in header) + ('name' in header) + ('path' in header)
    if expected > 1:
        raise InvalidCodebook(
            _f("Not sure which column to use for tag name"),
        )
    elif expected == 0:
        raise InvalidCodebook(_f("No 'tag', 'name', or 'path' column"))
    else:
        if 'tag' in header:
            col_path = header.index('tag')
        elif 'name' in header:
            col_path = header.index('name')
        else:
            col_path = header.index('path')

    # Is there a description?
    try:
        col_description = header.index('description')
    except ValueError:
        col_description = None

    # Read file
    try:
        tags = []
        for row in reader:
            path = row[col_path]
            if col_description is not None:
                description = row[col_description]
            else:
                description = ''
            tags.append({'path': path, 'description': description})
    except (csv.Error, UnicodeDecodeError):
        raise InvalidCodebook(_f("Invalid CSV file"))

    return tags


def list_tags(reader):
    return list_tags_csv(reader)
