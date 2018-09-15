import json
import logging
import jinja2
import os

from sqlalchemy.orm import joinedload
from tornado.web import authenticated, HTTPError, RequestHandler
import tornado.ioloop
import tornado.web
from tornado.routing import URLSpec

from . import database


logger = logging.getLogger(__name__)


DBSession = database.connect()


class BaseHandler(RequestHandler):
    """Base class for all request handlers.
    """
    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            [os.path.join(os.path.dirname(__file__), 'templates')]
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
        self.db = DBSession()

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
        return project_member.project

    def get_json(self):
        type_ = self.request.headers.get('Content-Type', '')
        if not type_.startswith('application/json'):
            raise HTTPError(400, "Expected JSON")
        return json.loads(self.request.body)

    def send_json(self, obj):
        if isinstance(obj, list):
            obj = {'results': obj}
        elif not isinstance(obj, dict):
            raise ValueError("Can't encode %r to JSON" % type(obj))
        self.set_header('Content-Type', 'text/json; charset=utf-8')
        return self.finish(json.dumps(obj))


class Index(BaseHandler):
    """Index page, shows welcome message and user's projects.
    """
    def get(self):
        if self.current_user is not None:
            user = self.db.query(database.User).get(self.current_user)
            if user is None:
                logger.warning("User is logged in as non-existent user %r",
                               self.current_user)
                self.logout()
            else:
                self.render('index.html', user=user, projects=user.projects)
                return
        self.render('welcome.html')


class Login(BaseHandler):
    def get(self):
        self.login('admin')
        self.redirect(self.get_argument('next', self.reverse_url('index')))
        # TODO: Actual login form


class Logout(BaseHandler):
    def get(self):
        self.logout()
        self.redirect(self.reverse_url('index'))


class NewProject(BaseHandler):
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
        project = database.Project(name=name, description=description)
        self.db.add(project)
        membership = database.ProjectMember(
            project=project,
            user_login=self.current_user,
            privileges=database.Privileges.ADMIN
        )
        self.db.add(membership)
        self.db.commit()
        self.redirect(self.reverse_url('project', project.id))

    def render(self, template_name, **kwargs):
        for name in ('name', 'description', 'error'):
            kwargs.setdefault(name, '')
        super(NewProject, self).render(template_name, **kwargs)


class Project(BaseHandler):
    @authenticated
    def get(self, project_id):
        self.render('project.html', project=self.get_project(project_id))


class ProjectMeta(BaseHandler):
    @authenticated
    def post(self, project_id):
        obj = self.get_json()
        project = self.get_project(project_id)
        project.name = obj['name']
        project.description = obj['description']
        logger.info("Updated project: %r %r",
                    project.name, project.description)
        self.db.commit()
        return self.send_json({})


class ProjectDocuments(BaseHandler):
    @authenticated
    def get(self, project_id):
        project = self.get_project(project_id)
        return self.send_json({
            'documents': [
                {'name': doc.name}
                for doc in project.documents
            ]
        })


app = tornado.web.Application(
    [
        URLSpec('/', Index, name='index'),
        URLSpec('/login', Login, name='login'),
        URLSpec('/logout', Logout, name='logout'),
        URLSpec('/new', NewProject, name='new_project'),
        URLSpec('/project/([0-9]+)', Project, name='project'),
        URLSpec('/project/([0-9]+)/meta', ProjectMeta),
        URLSpec('/project/([0-9]+)/documents', ProjectDocuments),
    ],
    static_path=os.path.join(os.path.dirname(__file__), 'static'),
    login_url='/login',
    xsrf_cookies=True,
    debug=True,
    cookie_secret='TODO:_cookie_here_',
)


def main():
    logging.basicConfig(level=logging.INFO)
    app.listen(8000)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
