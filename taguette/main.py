import argparse
import logging
import os
import re
import sys
import tornado.ioloop
from urllib.parse import urlparse
import webbrowser

from . import __version__
from .database import migrate
from .web import make_app


def prepare_db(database):
    # Windows paths kinda look like URLs, but aren't
    if sys.platform == 'win32' and re.match(r'^[a-zA-Z]:\\', database):
        url = None
    else:
        url = urlparse(database)
    if url is not None and url.scheme:
        # Full URL: use it, create path if sqlite
        db_url = database
        if url.scheme == 'sqlite' and url.path.startswith('/'):
            os.makedirs(url.path[1:])
    else:
        # Path: create it, turn into URL
        os.makedirs(os.path.dirname(database), exist_ok=True)
        db_url = 'sqlite:///' + database
    return db_url


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
    parser.add_argument('--singleuser', action='store_false', default=False,
                        dest='multiuser',
                        help="Run in single-user mode (default)")
    parser.add_argument('--multiuser', action='store_true', default=False,
                        help="Run in multi-user mode")
    parser.add_argument('--enable-register', dest='register',
                        action='store_true', default=True,
                        help=argparse.SUPPRESS)
    parser.add_argument('--disable-register', dest='register',
                        action='store_false', default=True,
                        help=argparse.SUPPRESS)
    parser.add_argument('--xheaders', action='store_true', default=False,
                        help="Read X-Forwarded-For header (if using a reverse "
                             "proxy)")
    parser.set_defaults(func=None)

    subparsers = parser.add_subparsers(title="additional commands", metavar='')

    parser_migrate = subparsers.add_parser('migrate',
                                           help="Manually trigger a database "
                                                "migration")
    parser_migrate.add_argument('revision', action='store', default='head',
                                nargs=argparse.OPTIONAL)
    parser_migrate.set_defaults(
        func=lambda args: migrate(prepare_db(args.database), args.revision))

    args = parser.parse_args()

    if args.func:
        args.func(args)
        sys.exit(0)

    address = args.bind
    port = int(args.port)

    db_url = prepare_db(args.database)

    app = make_app(db_url, multiuser=args.multiuser,
                   register_enabled=args.register, debug=args.debug)
    app.listen(port, address=address, xheaders=args.xheaders)
    loop = tornado.ioloop.IOLoop.current()

    token = app.single_user_token
    if token:
        url = 'http://localhost:%d/?token=%s' % (port, token)
    else:
        url = 'http://localhost:%d/' % port
    print("\n    Taguette is now running. You can connect to it using this "
          "link:\n\n    %s\n" % url)

    if args.browser and not args.debug:
        loop.call_later(0.01, webbrowser.open, url)

    loop.start()


if __name__ == '__main__':
    main()
