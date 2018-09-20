import asyncio
from datetime import datetime
import json
import logging
import jinja2
import os
from sqlalchemy.orm import joinedload, undefer, make_transient
from tornado.concurrent import Future
import tornado.ioloop
from tornado.routing import URLSpec
from tornado.web import authenticated, HTTPError, RequestHandler

from . import convert
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

    def get_document(self, project_id, document_id, contents=False):
        try:
            project_id = int(project_id)
            document_id = int(document_id)
        except ValueError:
            raise HTTPError(404)

        q = (
            self.db.query(database.Document)
            .options(joinedload(database.Document.project)
                     .joinedload(database.Project.members))
            .filter(database.Project.id == project_id)
            .filter(database.ProjectMember.user_login == self.current_user)
            .filter(database.Document.id == document_id)
        )
        if contents:
            q = q.options(undefer(database.Document.contents))
        document = q.one_or_none()
        if document is None:
            raise HTTPError(404)
        return document

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
        self.db.add(database.HlTag(project=project, path='interesting',
                                   description="Further review required"))
        self.db.add(database.HlTag(project=project, path='people',
                                   description="Known people"))
        self.db.add(database.HlTag(project=project, path='people.devs',
                                   description="Software developers"))
        self.db.add(database.HlTag(project=project, path='people.family',
                                   description="Family mentions"))
        self.db.add(database.HlTag(project=project, path='people.family.father',
                                   description="Mothers"))
        self.db.add(database.HlTag(project=project, path='people.family.mother',
                                   description="Fathers"))

        self.db.commit()
        self.redirect(self.reverse_url('project', project.id))

    def render(self, template_name, **kwargs):
        for name in ('name', 'description', 'error'):
            kwargs.setdefault(name, '')
        super(NewProject, self).render(template_name, **kwargs)


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
        hltags_json = jinja2.Markup(json.dumps(
            {
                str(hltag.id): {'id': hltag.id,
                             'path': hltag.path,
                             'description': hltag.description}
                for hltag in project.hltags
            },
            sort_keys=True,
        ))
        self.render('project.html',
                    project=project,
                    last_event=js_timestamp(project.last_event),
                    documents=documents_json,
                    hltags=hltags_json)


def js_timestamp(dt=None):
    if dt is None:
        dt = datetime.utcnow()
    return int(dt.timestamp())


class ProjectMeta(BaseHandler):
    @authenticated
    def post(self, project_id):
        obj = self.get_json()
        project = self.get_project(project_id)
        project.name = obj['name']
        project.description = obj['description']
        now = datetime.utcnow()
        project.meta_updated = now
        logger.info("Updated project: %r %r",
                    project.name, project.description)
        cmd = database.Command.project_meta(
            self.current_user,
            project.id,
            obj['name'],
            obj['description'],
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(project.id, cmd)
        return self.send_json({'ts': js_timestamp(now)})


class DocumentAdd(BaseHandler):
    @authenticated
    async def post(self, project_id):
        project = self.get_project(project_id)

        name = self.get_body_argument('name')
        description = self.get_body_argument('description')
        file = self.request.files['file'][0]
        content_type = file.content_type

        try:
            body = await convert.to_html_chunks(file.body, content_type,
                                                file.filename)
        except convert.ConversionError as err:
            self.set_status(400)
            self.send_json({
                'error': str(err),
            })
        else:
            doc = database.Document(
                name=name,
                description=description,
                filename=file.filename or None,
                project=project,
                contents=body,
            )
            self.db.add(doc)
            project.documents_updated = datetime.utcnow()
            cmd = database.Command.document_add(
                self.current_user,
                doc,
            )
            self.db.add(cmd)
            logger.info("Document added to project %r: %r %r (%d bytes)",
                        project.id, doc.id, doc.name, len(doc.contents))
            self.db.commit()
            self.db.refresh(cmd)
            self.application.notify_project(project.id, cmd)
            self.send_json({'created': doc.id})


class DocumentContents(BaseHandler):
    @authenticated
    def get(self, project_id, document_id):
        document = self.get_document(project_id, document_id, True)
        self.send_json({
            'contents': [
                {'offset': 0, 'contents': document.contents},
            ],
            'highlights': [
                {'id': hl.id,
                 'start_offset': hl.start_offset,
                 'end_offset': hl.end_offset}
                for hl in document.highlights
            ],
        })


class HighlightAdd(BaseHandler):
    @authenticated
    def post(self, project_id, document_id):
        obj = self.get_json()
        document = self.get_document(project_id, document_id)
        hl = database.Highlight(document=document,
                                start_offset=obj['start_offset'],
                                end_offset=obj['end_offset'])
        self.db.add(hl)
        # TODO: hltags
        self.db.commit()  # Need to commit to get hl.id
        cmd = database.Command.highlight_add(
            self.current_user,
            document,
            hl,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(document.project_id, cmd)

        self.send_json({'id': hl.id})


class HighlightUpdate(BaseHandler):
    @authenticated
    def post(self, project_id, document_id, highlight_id):
        obj = self.get_json()
        document = self.get_document(project_id, document_id)
        hl = self.db.query(database.Highlight).get(int(highlight_id))
        if hl.document_id != document.id:
            raise HTTPError(404)
        if not obj:
            self.db.delete(hl)
            cmd = database.Command.highlight_delete(
                self.current_user,
                document,
                hl.id,
            )
        else:
            if 'start_offset' in obj:
                hl.start_offset = obj['start_offset']
            if 'end_offset' in obj:
                hl.end_offset = obj['end_offset']
            # TODO: hltags
            cmd = database.Command.highlight_add(
                self.current_user,
                document,
                hl,
            )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(document.project_id, cmd)

        self.send_json({'id': hl.id})


class ProjectEvents(BaseHandler):
    @authenticated
    async def get(self, project_id):
        from_ts = int(self.get_query_argument('from'))
        from_dt = datetime.utcfromtimestamp(from_ts)
        project = self.get_project(project_id)
        self.project_id = int(project_id)

        # Check for immediate update
        cmd = (
            self.db.query(database.Command)
            .filter(database.Command.date > from_dt)
        ).one_or_none()

        # Wait for an event
        if cmd is None:
            self.wait_future = Future()
            self.application.observe_project(project.id, self.wait_future)
            self.db.expire_all()
            try:
                cmd = await self.wait_future
            except asyncio.CancelledError:
                return

        payload = dict(cmd.payload)
        type_ = payload.pop('type', None)
        if type_ == 'project_meta':
            result = {'project_meta': payload}
        elif type_ == 'document_add':
            payload['id'] = cmd.document_id
            result = {'document_add': [payload]}
        elif type_ == 'highlight_add':
            result = {'highlight_add': {cmd.document_id: [payload]}}
        elif type_ == 'highlight_delete':
            result = {
                'highlight_delete': {cmd.document_id: [payload['id']]}
            }
        else:
            raise ValueError("Unknown command type %r" % type_)

        result['ts'] = js_timestamp(cmd.date)
        self.send_json(result)

    def on_connection_close(self):
        self.wait_future.cancel()
        self.application.unobserve_project(self.project_id, self.wait_future)


class Application(tornado.web.Application):
    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(*args, **kwargs)

        self.event_waiters = {}

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


def make_app():
    return Application(
        [
            URLSpec('/', Index, name='index'),
            URLSpec('/login', Login, name='login'),
            URLSpec('/logout', Logout, name='logout'),
            URLSpec('/new', NewProject, name='new_project'),
            URLSpec('/project/([0-9]+)', Project, name='project'),
            URLSpec('/project/([0-9]+)/document/[0-9]+', Project,
                    name='project_doc'),
            URLSpec('/project/([0-9]+)/tag/[0-9]+', Project,
                    name='project_tag'),
            URLSpec('/project/([0-9]+)/meta', ProjectMeta),
            URLSpec('/project/([0-9]+)/document/new', DocumentAdd),
            URLSpec('/project/([0-9]+)/document/([0-9]+)/content',
                    DocumentContents),
            URLSpec('/project/([0-9]+)/document/([0-9]+)/highlight/new',
                    HighlightAdd),
            URLSpec('/project/([0-9]+)/document/([0-9]+)/highlight/([0-9]+)',
                    HighlightUpdate),
            URLSpec('/project/([0-9]+)/events', ProjectEvents),
        ],
        static_path=os.path.join(os.path.dirname(__file__), 'static'),
        login_url='/login',
        xsrf_cookies=True,
        debug=True,
        cookie_secret='TODO:_cookie_here_',
    )


def main():
    logging.basicConfig(level=logging.INFO)
    app = make_app()
    app.listen(8000)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
