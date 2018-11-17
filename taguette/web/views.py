import json
import logging
import jinja2
from markupsafe import Markup
from sqlalchemy.orm import aliased
from tornado.web import authenticated, HTTPError

from .. import database
from .base import BaseHandler


logger = logging.getLogger(__name__)


class Index(BaseHandler):
    """Index page, shows welcome message and user's projects.
    """
    def get(self):
        if self.current_user is not None:
            if self.get_query_argument('token', None):
                self.redirect(self.reverse_url('index'))
                return
            user = self.db.query(database.User).get(self.current_user)
            if user is None:
                logger.warning("User is logged in as non-existent user %r",
                               self.current_user)
                self.logout()
            else:
                messages = []
                if self.current_user == 'admin':
                    messages = [Markup(msg['html'])
                                for msg in self.application.messages]
                self.render('index.html', user=user, projects=user.projects,
                            messages=messages)
                return
        elif not self.application.config['MULTIUSER']:
            token = self.get_query_argument('token', None)
            if token and token == self.application.single_user_token:
                self.login('admin')
                self.redirect(self.reverse_url('index'))
            elif token:
                self.redirect(self.reverse_url('index'))
            else:
                self.render('token_needed.html')
        else:
            self.render('welcome.html')


class Login(BaseHandler):
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        if self.current_user:
            self._go_to_next()
        else:
            self.render('login.html', register=False,
                        next=self.get_argument('next', ''))

    def post(self):
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
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        self.logout()
        self.redirect(self.reverse_url('index'))


class Register(BaseHandler):
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        if not self.application.config['REGISTRATION_ENABLED']:
            raise HTTPError(403)
        if self.current_user:
            self.redirect(self.reverse_url('index'))
        else:
            self.render('login.html', register=True)

    def post(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        if not self.application.config['REGISTRATION_ENABLED']:
            raise HTTPError(403)
        login = self.get_body_argument('login')
        password1 = self.get_body_argument('password1')
        password2 = self.get_body_argument('password2')
        email = self.get_body_argument('email', '')
        if password1 != password2:
            self.render('login.html', register=True,
                        register_error="Passwords do not match")
            return
        if self.db.query(database.User).get(login) is not None:
            self.render('login.html', register=True,
                        register_error="Username is taken")
            return
        if (email and
                self.db.query(database.User)
                .filter(database.User.email == email).count() > 0):
            self.render('login.html', register=True,
                        register_error="Email is already used")
            return
        user = database.User(login=login)
        user.set_password(password1)
        if email:
            user.email = email
        self.db.add(user)
        self.db.commit()
        logger.info("User registered: %r", login)
        self.set_secure_cookie('user', login)
        self.redirect(self.reverse_url('index'))


class ProjectAdd(BaseHandler):
    @authenticated
    def get(self):
        self.render('project_new.html')

    @authenticated
    def post(self):
        name = self.get_body_argument('name', '')
        description = self.get_body_argument('description', '')
        if not name:
            return self.render('project_new.html',
                               name=name, description=description,
                               error="Please enter a name")

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

    def render(self, template_name, **kwargs):
        for name in ('name', 'description', 'error'):
            kwargs.setdefault(name, '')
        super(ProjectAdd, self).render(template_name, **kwargs)


class ProjectDelete(BaseHandler):
    def get(self, project_id):
        project = self.get_project(project_id)
        doc = aliased(database.Document)
        highlights = (
            self.db.query(database.Highlight)
            .join(doc, database.Highlight.document_id == doc.id)
            .filter(doc.project_id == project.id)
        ).count()
        self.render('project_delete.html', project=project,
                    documents=len(project.documents), tags=len(project.tags),
                    highlights=highlights)

    def post(self, project_id):
        project = self.get_project(project_id)
        logger.warning("Deleting project %d %r user=%r",
                       project.id, project.name, self.current_user)
        self.db.delete(project)
        self.db.commit()
        self.redirect(self.reverse_url('index'))


class Project(BaseHandler):
    @authenticated
    def get(self, project_id):
        project = self.get_project(project_id)
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
        self.render('project.html',
                    project=project,
                    last_event=(project.last_event
                                if project.last_event is not None
                                else -1),
                    documents=documents_json,
                    tags=tags_json)
