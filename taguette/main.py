import argparse
import logging
import os
import re
import sys
import tornado.ioloop
from urllib.parse import urlparse
import webbrowser

from . import __version__
from .web import make_app


def main():
    logging.root.handlers.clear()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")

    if sys.platform == 'win32':
        import ctypes.wintypes

        CSIDL_PERSONAL = 5  # My Documents
        SHGFP_TYPE_CURRENT = 0  # Get current, not default value

        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None,
                                               SHGFP_TYPE_CURRENT, buf)

        default_db = os.path.join(buf.value, 'Taguette', 'taguette.sqlite3')
        default_db_show = os.path.join(os.path.basename(buf.value),
                                       'Taguette', 'taguette.sqlite3')
    else:
        data = os.environ.get('XDG_DATA_HOME')
        if not data:
            data = os.path.join(os.environ['HOME'], '.local', 'share')
            default_db_show = '$HOME/.local/share/taguette/taguette.sqlite3'
        else:
            default_db_show = '$XDG_DATA_HOME/taguette/taguette.sqlite3'
        default_db = os.path.join(data, 'taguette', 'taguette.sqlite3')

    parser = argparse.ArgumentParser(
        description="Document tagger for qualitative analysis",
    )
    parser.add_argument('--version', action='version',
                        version='taguette version %s' % __version__)
    parser.add_argument('-p', '--port', default='8000',
                        help="Port number on which to listen")
    parser.add_argument('-b', '--bind', default='127.0.0.1',
                        help="Address to bind on")
    parser.add_argument('--browser', action='store_true', default=True,
                        help="Open web browser to the application")
    parser.add_argument('--no-browser', action='store_false', dest='browser',
                        help="Don't open the web browser")
    parser.add_argument('--debug', action='store_true', default=False,
                        help=argparse.SUPPRESS)
    parser.add_argument('--database', action='store',
                        default=default_db,
                        help="Database location or connection string, for "
                             "example 'project.db' or "
                             "'postgresql://me:pw@localhost/mydb' "
                             "(default: %r)" % default_db_show)
    args = parser.parse_args()
    address = args.bind
    port = int(args.port)

    # Windows paths kinda look like URLs, but aren't
    if sys.platform == 'win32' and re.match(r'^[a-zA-Z]:\\', args.database):
        url = None
    else:
        url = urlparse(args.database)
    if url is not None and url.scheme:
        # Full URL: use it, create path if sqlite
        db_url = args.database
        if url.scheme == 'sqlite' and url.path.startswith('/'):
            os.makedirs(url.path[1:])
    else:
        # Path: create it, turn into URL
        os.makedirs(os.path.dirname(args.database), exist_ok=True)
        db_url = 'sqlite:///' + args.database

    app = make_app(db_url, args.debug)
    app.listen(port, address=address)
    loop = tornado.ioloop.IOLoop.current()
    if args.browser and not args.debug:
        loop.call_later(0.01, webbrowser.open, 'http://localhost:%d/' % port)
    loop.start()


if __name__ == '__main__':
    main()
