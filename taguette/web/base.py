import asyncio
import contextlib
import functools
import hashlib
import hmac
import json
import logging
import jinja2
import os
import pkg_resources
from prometheus_async.aio import time as prom_async_time
import smtplib
from sqlalchemy.orm import joinedload, undefer, make_transient
import tornado.ioloop
from tornado.httpclient import AsyncHTTPClient
import tornado.locale
import tornado.iostream
from tornado.web import HTTPError, RequestHandler
from urllib.parse import urlencode

from .. import __version__ as version
from .. import database


logger = logging.getLogger(__name__)


class PseudoLocale(tornado.locale.Locale):
    def __init__(self):
        super().__init__('qps-ploc')

    CHARS = {
        'A': '\u00c5', 'B': '\u0181', 'C': '\u00c7', 'D': '\u00d0',
        'E': '\u00c9', 'F': '\u0191', 'G': '\u011c', 'H': '\u0124',
        'I': '\u00ce', 'J': '\u0134', 'K': '\u0136', 'L': '\u013b',
        'M': '\u1e40', 'N': '\u00d1', 'O': '\u00d6', 'P': '\u00de',
        'Q': '\u01ea', 'R': '\u0154', 'S': '\u0160', 'T': '\u0162',
        'U': '\u00db', 'V': '\u1e7c', 'W': '\u0174', 'X': '\u1e8a',
        'Y': '\u00dd', 'Z': '\u017d', 'a': '\u00e5', 'b': '\u0180',
        'c': '\u00e7', 'd': '\u00f0', 'e': '\u00e9', 'f': '\u0192',
        'g': '\u011d', 'h': '\u0125', 'i': '\u00ee', 'j': '\u0135',
        'k': '\u0137', 'l': '\u013c', 'm': '\u0271', 'n': '\u00f1',
        'o': '\u00f6', 'p': '\u00fe', 'q': '\u01eb', 'r': '\u0155',
        's': '\u0161', 't': '\u0163', 'u': '\u00fb', 'v': '\u1e7d',
        'w': '\u0175', 'x': '\u1e8b', 'y': '\u00fd', 'z': '\u017e',
        ' ': '\u2003',
    }

    @functools.lru_cache()
    def mangle(self, text):
        out = []
        i = 0
        while i < len(text):
            if text[i] == '{' and text[i + 1] == '{':
                # Jinja2 variable
                j = i + 2
                while text[j] != '}':
                    j += 1
                j += 1
                out.append(text[i:j + 1])
                i = j
            elif text[i] == '%' and text[i + 1] == '(':
                # Python variable
                j = i + 2
                while text[j] != ')':
                    j += 1
                j += 1
                assert text[j] in 'srdf'
                out.append(text[i:j + 1])
                i = j
            elif text[i] == '<':
                # HTML tag
                j = i + 1
                while text[j] != '>':
                    j += 1
                out.append(text[i:j + 1])
                i = j
            else:
                out.append(self.CHARS.get(text[i], text[i]))
            i += 1

        return ''.join(out)

    def translate(self, message, plural_message=None, count=None):
        if plural_message is not None:
            assert count is not None
            return '[%s (n=%d)]' % (
                self.mangle(plural_message),
                count,
            )
        else:
            assert count is None
            return '[%s]' % self.mangle(message)

    def pgettext(self, context, message, plural_message=None, count=None):
        return self.translate(message, plural_message, count)


class Application(tornado.web.Application):
    def __init__(self, handlers,
                 config, **kwargs):
        self.config = config

        # Don't reuse the secret
        cookie_secret = config['SECRET_KEY']

        super(Application, self).__init__(handlers,
                                          cookie_secret=cookie_secret,
                                          **kwargs)

        d = pkg_resources.resource_filename('taguette', 'l10n')
        tornado.locale.load_gettext_translations(d, 'taguette_main')
        tornado.locale.set_default_locale(self.config['DEFAULT_LANGUAGE'])

        self.DBSession = database.connect(config['DATABASE'])
        self.event_waiters = {}

        db = self.DBSession()
        admin = (
            db.query(database.User)
            .filter(database.User.login == 'admin')
            .one_or_none()
        )
        if admin is None:
            logger.warning("Creating user 'admin'")
            admin = database.User(login='admin')
            if config['MULTIUSER']:
                self._set_password(admin)
            db.add(admin)
            db.commit()
        elif config['MULTIUSER'] and not admin.hashed_password:
            self._set_password(admin)
            db.commit()
        db.close()

        if config['TOS_FILE']:
            with open(config['TOS_FILE']) as fp:
                self.terms_of_service = fp.read()
        else:
            self.terms_of_service = None

        if config['MULTIUSER']:
            self.single_user_token = None
            logger.info("Starting in multi-user mode")
            if not self.terms_of_service:
                logger.warning("No terms of service set")
        else:
            self.single_user_token = hmac.new(
                cookie_secret.encode('utf-8'),
                b'taguette_single_user',
                digestmod=hashlib.sha256,
            ).hexdigest()

        # Get messages from taguette.org
        self.messages = []
        self.messages_event = asyncio.Event()
        self.check_messages()

    async def _check_messages(self):
        http_client = AsyncHTTPClient()
        response = await http_client.fetch(
            'https://msg.taguette.org/%s' % version,
            headers={'Accept': 'application/json', 'User-Agent': 'Taguette'})
        obj = json.loads(response.body.decode('utf-8'))
        self.messages = obj['messages']
        for msg in self.messages:
            logger.warning("Taguette message: %s", msg['text'])
        self.messages_event.set()

    @staticmethod
    def _check_messages_callback(future):
        try:
            future.result()
        except Exception:
            logger.exception("Error getting messages")

    def check_messages(self):
        f_msg = asyncio.get_event_loop().create_task(self._check_messages())
        f_msg.add_done_callback(self._check_messages_callback)
        asyncio.get_event_loop().call_later(86400,  # 24 hours
                                            self.check_messages)

    def _set_password(self, user):
        import getpass
        passwd = getpass.getpass("Enter password for user %r: " % user.login)
        user.set_password(passwd)

    def observe_project(self, project_id, future):
        assert isinstance(project_id, int)
        self.event_waiters.setdefault(project_id, set()).add(future)

    def unobserve_project(self, project_id, future):
        assert isinstance(project_id, int)
        if project_id in self.event_waiters:
            self.event_waiters[project_id].discard(future)

    def notify_project(self, project_id, cmd):
        assert isinstance(project_id, int)
        make_transient(cmd)
        for future in self.event_waiters.pop(project_id, []):
            future.set_result(cmd)

    def send_mail(self, msg):
        config = self.config['MAIL_SERVER']
        if config.get('ssl', False):
            cls = smtplib.SMTP_SSL
        else:
            cls = smtplib.SMTP
        with cls(config['host'], config.get('port', 25)) as smtp:
            if 'user' in config or 'password' in config:
                smtp.login(config['user'], config['password'])
            smtp.send_message(msg)

    def log_request(self, handler):
        if "log_function" in self.settings:
            self.settings["log_function"](handler)
            return
        access_log = logging.getLogger("tornado.access")
        if handler.get_status() < 400:
            log_method = access_log.info
        elif handler.get_status() < 500:
            log_method = access_log.warning
        else:
            log_method = access_log.error
        request_time = 1000.0 * handler.request.request_time()
        log_method(
            "%d %s %.2fms (%s) lang=%s",
            handler.get_status(),
            handler._request_summary(),
            request_time,
            handler.current_user,
            handler.request.headers.get('Accept-Language'),
        )


class BaseHandler(RequestHandler):
    """Base class for all request handlers.
    """
    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            [pkg_resources.resource_filename('taguette', 'templates')]
        ),
        autoescape=jinja2.select_autoescape(['html']),
        extensions=['jinja2.ext.i18n'],
    )

    @jinja2.contextfunction
    def _tpl_static_url(context, path):
        v = not context['handler'].application.settings.get('debug', False)
        return context['handler'].static_url(path, include_version=v)
    template_env.globals['static_url'] = _tpl_static_url

    @jinja2.contextfunction
    def _tpl_reverse_url(context, path, *args):
        return context['handler'].reverse_url(path, *args)
    template_env.globals['reverse_url'] = _tpl_reverse_url

    @jinja2.contextfunction
    def _tpl_xsrf_form_html(context):
        return jinja2.Markup(context['handler'].xsrf_form_html())
    template_env.globals['xsrf_form_html'] = _tpl_xsrf_form_html

    def __init__(self, application, request, **kwargs):
        super(BaseHandler, self).__init__(application, request, **kwargs)
        self._db = None
        self._gettext = None

    def set_default_headers(self):
        self.set_header('Server', 'Taguette/%s' % version)

    @property
    def db(self):
        if self._db is None:
            self._db = self.application.DBSession()
        return self._db

    def on_finish(self):
        super(BaseHandler, self).on_finish()
        self.close_db_connection()

    def close_db_connection(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def gettext(self, message, **kwargs):
        trans = self.locale.translate(message)
        if kwargs:
            trans = trans % kwargs
        return trans

    def ngettext(self, singular, plural, n, **kwargs):
        trans = self.locale.translate(singular, plural, n)
        if kwargs:
            trans = trans % kwargs
        return trans

    def get_current_user(self):
        user = self.get_secure_cookie('user')
        if user is not None:
            return user.decode('utf-8')
        else:
            return None

    def set_cookie(self, name, value, domain=None,
                   expires=None, path='/', expires_days=None,
                   *, dont_check=False,
                   **kwargs):
        if (
            dont_check
            or not self.application.config['COOKIES_PROMPT']
            or self.get_cookie('cookies_accepted')
            or self.get_cookie('user')
        ):
            return super(BaseHandler, self).set_cookie(name, value, **kwargs)
        else:
            self.redirect(
                self.reverse_url('cookies_prompt') +
                '?' +
                urlencode(dict(next=self.request.uri)),
            )
            raise HTTPError(302)

    if os.environ.get('TAGUETTE_TEST_LOCALE') == 'y':
        _pseudolocale = PseudoLocale()

        def get_user_locale(self):
            return self._pseudolocale
    else:
        def get_user_locale(self):
            language = self.get_secure_cookie('language')
            if language is not None:
                language = language.decode('utf-8')
            elif self.current_user is not None:
                user = self.db.query(database.User).get(self.current_user)
                if user is not None and user.language is not None:
                    language = user.language
                    self.set_secure_cookie('language', language)

            if language is not None:
                return tornado.locale.get(language)

    def login(self, username):
        logger.info("Logged in as %r", username)
        self.set_secure_cookie('user', username)

    def logout(self):
        logger.info("Logged out")
        self.clear_cookie('user')
        self.clear_cookie('language')

    def render_string(self, template_name, **kwargs):
        template = self.template_env.get_template(template_name)
        return template.render(
            handler=self,
            current_user=self.current_user,
            multiuser=self.application.config['MULTIUSER'],
            register_enabled=self.application.config['REGISTRATION_ENABLED'],
            tos=self.application.terms_of_service is not None,
            show_messages=self.current_user == 'admin',
            version=version,
            gettext=self.gettext,
            ngettext=self.ngettext,
            **kwargs)

    def get_project(self, project_id):
        try:
            project_id = int(project_id)
        except ValueError:
            raise HTTPError(404)
        project_member = (
            self.db.query(database.ProjectMember)
            .options(joinedload(database.ProjectMember.project))
            .get((project_id, self.current_user))
        )
        if project_member is None:
            raise HTTPError(404)
        return project_member.project, project_member.privileges

    def get_document(self, project_id, document_id, contents=False):
        try:
            project_id = int(project_id)
            document_id = int(document_id)
        except ValueError:
            raise HTTPError(404)

        q = (
            self.db.query(database.ProjectMember, database.Document)
            .filter(database.Document.project_id == project_id)
            .filter(database.Document.id == document_id)
            .filter(database.ProjectMember.user_login == self.current_user)
            .filter(database.ProjectMember.project_id == project_id)
        )
        if contents:
            q = q.options(undefer(database.Document.contents))
        res = q.one_or_none()
        if res is None:
            raise HTTPError(404)
        member, document = res
        return document, member.privileges

    def get_json(self):
        type_ = self.request.headers.get('Content-Type', '')
        if not type_.startswith('application/json'):
            raise HTTPError(400, "Expected JSON")
        try:
            return json.loads(self.request.body.decode('utf-8'))
        except json.JSONDecodeError:
            raise HTTPError(400, "Invalid JSON")

    def send_json(self, obj):
        if isinstance(obj, list):
            obj = {'results': obj}
        elif not isinstance(obj, dict):
            raise ValueError("Can't encode %r to JSON" % type(obj))
        self.set_header('Content-Type', 'application/json; charset=utf-8')
        return self.finish(json.dumps(obj))

    def send_error_json(self, status, message, reason=None):
        self.set_status(status, reason)
        return self.send_json({'error': message})

    def log_exception(self, typ, value, tb):
        if isinstance(value, tornado.iostream.StreamClosedError):
            pass
        else:
            super(BaseHandler, self).log_exception(typ, value, tb)

    def write_error(self, status_code, **kwargs):
        # If database session has failed, can't use it to render the error
        self.close_db_connection()

        if self.settings.get('serve_traceback'):
            # Debug mode
            super(BaseHandler, self).write_error(status_code, **kwargs)
        elif status_code == 404:
            self.render(
                'error.html',
                error_title="Error 404",
                error_message="This page does not exist.",
            )
        else:
            self.render(
                'error.html',
                error_title="Error %d" % status_code,
                error_message=self._reason + ".",
            )


def _f(message):
    """Pass-through translation function.

    Marks a string for translation without translating it at run time.
    """
    return message


class PromMeasureRequest(object):
    def __init__(self, count, time):
        self.count = count
        self.time = time

    def _wrap(self, name, timer):
        counter = self.count.labels(name)
        timer = timer(self.time.labels(name))

        # Initialize count
        counter.inc(0)

        def decorator(func):
            @contextlib.wraps(func)
            def wrapper(*args, **kwargs):
                # Count requests
                counter.inc()
                return func(*args, **kwargs)

            return timer(wrapper)

        return decorator

    def sync(self, name):
        return self._wrap(name, lambda metric: metric.time())

    def async_(self, name):
        return self._wrap(name, lambda metric: prom_async_time(metric))
