from datetime import timedelta, datetime
from email.message import EmailMessage
import json
import logging
import jinja2
from markupsafe import Markup
import prometheus_client
from sqlalchemy.orm import aliased
from tornado.web import authenticated, HTTPError
from urllib.parse import urlunparse

from .. import database
from .. import validate
from .base import BaseHandler, send_mail


logger = logging.getLogger(__name__)


PROM_PAGE = prometheus_client.Counter(
    'pages_total',
    "Page requests",
    ['name'],
)


class Index(BaseHandler):
    """Index page, shows welcome message and user's projects.
    """
    PROM_PAGE.labels('index').inc(0)
    PROM_PAGE.labels('welcome').inc(0)
    PROM_PAGE.labels('token').inc(0)
    PROM_PAGE.labels('token_needed').inc(0)

    def get(self):
        if self.current_user is not None:
            if self.get_query_argument('token', None):
                PROM_PAGE.labels('token').inc()
                self.redirect(self.reverse_url('index'))
                return
            user = self.db.query(database.User).get(self.current_user)
            if user is None:
                PROM_PAGE.labels('index').inc()
                logger.warning("User is logged in as non-existent user %r",
                               self.current_user)
                self.logout()
            else:
                messages = []
                if self.current_user == 'admin':
                    messages = [Markup(msg['html'])
                                for msg in self.application.messages]
                PROM_PAGE.labels('index').inc()
                self.render('index.html', user=user, projects=user.projects,
                            messages=messages)
                return
        elif not self.application.config['MULTIUSER']:
            token = self.get_query_argument('token', None)
            if token and token == self.application.single_user_token:
                PROM_PAGE.labels('token').inc()
                self.login('admin')
                self.redirect(self.reverse_url('index'))
            elif token:
                PROM_PAGE.labels('token_needed').inc()
                self.redirect(self.reverse_url('index'))
            else:
                PROM_PAGE.labels('token_needed').inc()
                self.render('token_needed.html')
        else:
            PROM_PAGE.labels('welcome').inc()
            self.render('welcome.html')


class Login(BaseHandler):
    PROM_PAGE.labels('login').inc(0)

    def get(self):
        PROM_PAGE.labels('login').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        if self.current_user:
            self._go_to_next()
        else:
            self.render('login.html', register=False,
                        next=self.get_argument('next', ''))

    def post(self):
        PROM_PAGE.labels('login').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        login = self.get_body_argument('login')
        password = self.get_body_argument('password')
        user = self.db.query(database.User).get(login)
        if user is not None and user.check_password(password):
            self.login(user.login)
            self._go_to_next()
        else:
            self.render('login.html', register=False,
                        next=self.get_argument('next', ''),
                        login_error="Invalid login or password")

    def _go_to_next(self):
        next_ = self.get_argument('next')
        if not next_:
            next_ = self.reverse_url('index')
        self.redirect(next_)


class Logout(BaseHandler):
    PROM_PAGE.labels('logout').inc(0)

    def get(self):
        PROM_PAGE.labels('logout').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        self.logout()
        self.redirect(self.reverse_url('index'))


class Register(BaseHandler):
    PROM_PAGE.labels('register').inc(0)

    def get(self):
        PROM_PAGE.labels('register').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        if not self.application.config['REGISTRATION_ENABLED']:
            raise HTTPError(403)
        if self.current_user:
            self.redirect(self.reverse_url('index'))
        else:
            self.render('login.html', register=True)

    def post(self):
        PROM_PAGE.labels('register').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        if not self.application.config['REGISTRATION_ENABLED']:
            raise HTTPError(403)
        try:
            login = self.get_body_argument('login')
            password1 = self.get_body_argument('password1')
            password2 = self.get_body_argument('password2')
            validate.user_login(login)
            validate.user_password(password1)
            email = self.get_body_argument('email', '')
            if email:
                validate.user_email(email)
            if password1 != password2:
                raise validate.InvalidFormat("Passwords do not match")
            if self.db.query(database.User).get(login) is not None:
                raise validate.InvalidFormat("Username is taken")
            if (email and
                    self.db.query(database.User)
                    .filter(database.User.email == email).count() > 0):
                raise validate.InvalidFormat("Email is already used")
            user = database.User(login=login)
            user.set_password(password1)
            if email:
                user.email = email
            self.db.add(user)
            self.db.commit()
            logger.info("User registered: %r", login)
            self.set_secure_cookie('user', login)
            self.redirect(self.reverse_url('index'))
        except validate.InvalidFormat as e:
            logging.info("Error validating Register: %r", e)
            self.render('login.html', register=True,
                        register_error=e.message)


class Account(BaseHandler):
    PROM_PAGE.labels('account').inc(0)

    @authenticated
    def get(self):
        PROM_PAGE.labels('account').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        user = self.db.query(database.User).get(self.current_user)
        self.render('account.html', user=user)

    @authenticated
    def post(self):
        PROM_PAGE.labels('account').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        user = self.db.query(database.User).get(self.current_user)
        try:
            email = self.get_body_argument('email', None)
            password1 = self.get_body_argument('password1', None)
            password2 = self.get_body_argument('password2', None)
            if email is not None:
                validate.user_email(email)
                user.email = email
            if password1 is not None or password2 is not None:
                validate.user_password(password1)
                if password1 != password2:
                    raise validate.InvalidFormat("Passwords do not match")
                user.set_password(password1)
            self.db.commit()
            self.redirect(self.reverse_url('account'))
        except validate.InvalidFormat as e:
            logging.info("Error validating Account: %r", e)
            self.render('account.html', user=user,
                        error=e.message)


class AskResetPassword(BaseHandler):
    PROM_PAGE.labels('reset_password').inc(0)

    def get(self):
        PROM_PAGE.labels('reset_password').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        self.render('reset_password.html')

    def post(self):
        PROM_PAGE.labels('reset_password').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        email = self.get_body_argument('email')
        user = (
            self.db.query(database.User).filter(database.User.email == email)
        ).one_or_none()
        if user is None:
            return self.render(
                'reset_password.html',
                error="This email is not associated with any user",
            )
        elif (user.email_sent is None or
                user.email_sent + timedelta(days=1) < datetime.utcnow()):
            # Generate a signed token
            reset_token = self.create_signed_value('reset_token', user.email)
            reset_token = reset_token.decode('utf-8')

            # Reset link
            path = self.request.path
            if path.endswith('/reset_password'):
                path = path[:-15]
            path = path + '/new_password'
            reset_link = urlunparse([self.request.protocol,
                                     self.request.host,
                                     path,
                                     '',
                                     'reset_token=' + reset_token,
                                     ''])

            msg = EmailMessage()
            msg['Subject'] = "Password reset for Taguette"
            msg['From'] = self.application.config['EMAIL']
            msg['To'] = "{} <{}>".format(user.login, user.email)
            msg.set_content(self.render_string('email_reset_password.txt',
                                               link=reset_link))
            msg.add_alternative(self.render_string('email_reset_password.html',
                                                   link=reset_link),
                                subtype='html')

            send_mail(msg, self.application.config['MAIL_SERVER'])
            user.email_sent = datetime.utcnow()
            self.db.commit()
        self.render('reset_password.html', message="Email sent!")


class SetNewPassword(BaseHandler):
    PROM_PAGE.labels('new_password').inc(0)

    def get(self):
        PROM_PAGE.labels('new_password').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        reset_token = self.get_query_argument('reset_token')
        self.get_secure_cookie('reset_token', reset_token,
                               max_age_days=2).decode('utf-8')
        self.render('new_password.html', reset_token=reset_token)

    def post(self):
        PROM_PAGE.labels('new_password').inc()
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        reset_token = self.get_body_argument('reset_token')
        email = self.get_secure_cookie(
            'reset_token',
            reset_token,
            min_version=2,
            max_age_days=1,
        ).decode('utf-8')
        user = (
            self.db.query(database.User).filter(database.User.email == email)
        ).one_or_none()
        if not user:
            raise HTTPError(403)
        try:
            password1 = self.get_body_argument('password1')
            password2 = self.get_body_argument('password2')
            validate.user_password(password1)
            if password1 != password2:
                raise validate.InvalidFormat("Passwords do not match")
            user.set_password(password1)
            self.db.commit()
            return self.redirect(self.reverse_url('index'))
        except validate.InvalidFormat as e:
            logging.info("Error validating SetNewPassword: %r", e)
            return self.render('new_password.html', email=email,
                               error=e.message)


class ProjectAdd(BaseHandler):
    PROM_PAGE.labels('new_project').inc(0)

    @authenticated
    def get(self):
        PROM_PAGE.labels('new_project').inc()
        self.render('project_new.html')

    @authenticated
    def post(self):
        PROM_PAGE.labels('new_project').inc()
        name = self.get_body_argument('name', '')
        description = self.get_body_argument('description', '')
        try:
            validate.project_name(name)
            validate.project_description(description)

            # Create project
            project = database.Project(name=name, description=description)
            self.db.add(project)
            # Add user as admin
            membership = database.ProjectMember(
                project=project,
                user_login=self.current_user,
                privileges=database.Privileges.ADMIN
            )
            self.db.add(membership)
            # Add default set of tags
            self.db.add(database.Tag(project=project, path='interesting',
                                     description="Further review required"))
            self.db.add(database.Tag(project=project, path='people',
                                     description="Known people"))

            self.db.commit()
            self.redirect(self.reverse_url('project', project.id))
        except validate.InvalidFormat as e:
            logging.info("Error validating ProjectAdd: %r", e)
            self.render('project_new.html',
                        name=name, description=description,
                        error=e.message)

    def render(self, template_name, **kwargs):
        for name in ('name', 'description', 'error'):
            kwargs.setdefault(name, '')
        super(ProjectAdd, self).render(template_name, **kwargs)


class ProjectDelete(BaseHandler):
    PROM_PAGE.labels('delete_project').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_PAGE.labels('delete_project').inc()
        project, privileges = self.get_project(project_id)
        if not privileges.can_delete_project():
            raise HTTPError(403)
        doc = aliased(database.Document)
        highlights = (
            self.db.query(database.Highlight)
            .join(doc, database.Highlight.document_id == doc.id)
            .filter(doc.project_id == project.id)
        ).count()
        self.render('project_delete.html', project=project,
                    documents=len(project.documents), tags=len(project.tags),
                    highlights=highlights)

    @authenticated
    def post(self, project_id):
        PROM_PAGE.labels('delete_project').inc()
        project, privileges = self.get_project(project_id)
        if not privileges.can_delete_project():
            raise HTTPError(403)
        logger.warning("Deleting project %d %r user=%r",
                       project.id, project.name, self.current_user)
        self.db.delete(project)
        self.db.commit()
        self.redirect(self.reverse_url('index'))


class Project(BaseHandler):
    PROM_PAGE.labels('project').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_PAGE.labels('project').inc()
        project, _ = self.get_project(project_id)
        documents_json = jinja2.Markup(json.dumps(
            {
                str(doc.id): {'id': doc.id, 'name': doc.name,
                              'description': doc.description}
                for doc in project.documents
            },
            sort_keys=True,
        ))
        tags_json = jinja2.Markup(json.dumps(
            {
                str(tag.id): {'id': tag.id,
                              'path': tag.path,
                              'description': tag.description}
                for tag in project.tags
            },
            sort_keys=True,
        ))
        members = (
            self.db.query(database.ProjectMember)
            .filter(database.ProjectMember.project_id == project_id)
        ).all()
        members_json = jinja2.Markup(json.dumps(
            {member.user_login: {'privileges': member.privileges.name}
             for member in members}
        ))
        _ = self.xsrf_token  # Make sure XSRF cookie is set
        self.render('project.html',
                    project=project,
                    last_event=(project.last_event
                                if project.last_event is not None
                                else -1),
                    documents=documents_json,
                    user_login=jinja2.Markup(json.dumps(self.current_user)),
                    tags=tags_json,
                    members=members_json)
