import asyncio
import hashlib
import hmac
import json
import logging
import jinja2
import pkg_resources
import smtplib
from sqlalchemy.orm import joinedload, undefer, make_transient
import tornado.ioloop
from tornado.httpclient import AsyncHTTPClient
from tornado.web import HTTPError, RequestHandler

from .. import __version__ as version
from .. import database


logger = logging.getLogger(__name__)


class Application(tornado.web.Application):
    def __init__(self, handlers, cookie_secret,
                 config, **kwargs):
        self.config = config

        # Don't reuse the secret
        cookie_secret = cookie_secret + (
            '.multi' if config['MULTIUSER']
            else '.single'
        )

        super(Application, self).__init__(handlers,
                                          cookie_secret=cookie_secret,
                                          **kwargs)

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

        if config['MULTIUSER']:
            self.single_user_token = None
            logging.info("Starting in multi-user mode")
        else:
            self.single_user_token = hmac.new(
                cookie_secret.encode('utf-8'),
                b'taguette_single_user',
                digestmod=hashlib.sha256,
            ).hexdigest()

        # Get messages from taguette.org
        self.messages = []
        self.check_messages()

    async def _check_messages(self):
        http_client = AsyncHTTPClient()
        response = await http_client.fetch(
            'https://msg.taguette.org/%s' % version,
            headers={'Accept': 'application/json'})
        obj = json.loads(response.body.decode('utf-8'))
        self.messages = obj['messages']
        for msg in self.messages:
            logger.warning("Taguette message: %s", msg['text'])

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
        self.event_waiters[project_id].remove(future)

    def notify_project(self, project_id, cmd):
        assert isinstance(project_id, int)
        make_transient(cmd)
        for future in self.event_waiters.pop(project_id, []):
            future.set_result(cmd)


class BaseHandler(RequestHandler):
    """Base class for all request handlers.
    """
    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            [pkg_resources.resource_filename('taguette', 'templates')]
        ),
        autoescape=jinja2.select_autoescape(['html'])
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
        self.db = application.DBSession()

    def get_current_user(self):
        user = self.get_secure_cookie('user')
        if user is not None:
            return user.decode('utf-8')
        else:
            return None

    def login(self, username):
        logger.info("Logged in as %r", username)
        self.set_secure_cookie('user', username)

    def logout(self):
        logger.info("Logged out")
        self.clear_cookie('user')

    def render_string(self, template_name, **kwargs):
        template = self.template_env.get_template(template_name)
        return template.render(
            handler=self,
            current_user=self.current_user,
            multiuser=self.application.config['MULTIUSER'],
            register_enabled=self.application.config['REGISTRATION_ENABLED'],
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


def send_mail(msg, config):
    if config.get('ssl', False):
        cls = smtplib.SMTP_SSL
    else:
        cls = smtplib.SMTP
    with cls(config['host'], config.get('port', 25)) as smtp:
        if 'user' in config or 'password' in config:
            smtp.login(config['user'], config['password'])
        smtp.send_message(msg)
