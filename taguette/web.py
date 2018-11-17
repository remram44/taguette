import aiohttp
import asyncio
import bisect
import csv
import hashlib
import hmac
import io
import os
import json
import logging
import jinja2
from markupsafe import Markup
import pkg_resources
import re
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased, joinedload, undefer, make_transient
import sys
from tornado.concurrent import Future
import tornado.ioloop
from tornado.routing import URLSpec
from tornado.web import authenticated, HTTPError, RequestHandler

from . import __version__ as version
from . import convert
from . import database
from . import extract


logger = logging.getLogger(__name__)


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
            multiuser=self.application.multiuser,
            register_enabled=self.application.register_enabled,
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
        return json.loads(self.request.body.decode('utf-8'))

    def send_json(self, obj):
        if isinstance(obj, list):
            obj = {'results': obj}
        elif not isinstance(obj, dict):
            raise ValueError("Can't encode %r to JSON" % type(obj))
        self.set_header('Content-Type', 'application/json; charset=utf-8')
        return self.finish(json.dumps(obj))


def export_doc(wrapped):
    async def wrapper(self, *args):
        args, ext = args[:-1], args[-1]
        ext = ext.lower()
        name, html = wrapped(self, *args)
        mimetype, contents = convert.html_to(html, ext)
        self.set_header('Content-Type', mimetype)
        self.set_header('Content-Disposition',
                        'attachment; filename="%s.%s"' % (name, ext))
        for chunk in await contents:
            self.write(chunk)
        self.finish()
    return wrapper


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
        elif not self.application.multiuser:
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
        if not self.application.multiuser:
            raise HTTPError(404)
        if self.current_user:
            self._go_to_next()
        else:
            self.render('login.html', register=False,
                        next=self.get_argument('next', ''))

    def post(self):
        if not self.application.multiuser:
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
        if not self.application.multiuser:
            raise HTTPError(404)
        self.logout()
        self.redirect(self.reverse_url('index'))


class Register(BaseHandler):
    def get(self):
        if not self.application.multiuser:
            raise HTTPError(404)
        if not self.application.register_enabled:
            raise HTTPError(403)
        if self.current_user:
            self.redirect(self.reverse_url('index'))
        else:
            self.render('login.html', register=True)

    def post(self):
        if not self.application.multiuser:
            raise HTTPError(404)
        if not self.application.register_enabled:
            raise HTTPError(403)
        login = self.get_body_argument('login')
        password1 = self.get_body_argument('password1')
        password2 = self.get_body_argument('password2')
        if password1 != password2:
            self.render('login.html', register=True,
                        register_error="Passwords do not match")
            return
        if self.db.query(database.User).get(login) is not None:
            self.render('login.html', register=True,
                        register_error="Username is taken")
            return
        user = database.User(login=login)
        user.set_password(password1)
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


class ProjectMeta(BaseHandler):
    @authenticated
    def post(self, project_id):
        obj = self.get_json()
        project = self.get_project(project_id)
        project.name = obj['name']
        project.description = obj['description']
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
        return self.send_json({})


_windows_device_files = ('CON', 'AUX', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1',
                         'LPT2', 'LPT3', 'PRN', 'NUL')
_not_ascii_re = re.compile(r'[^A-Za-z0-9_.-]')


def secure_filename(name):
    """Sanitize a filename.

    This takes a filename, for example provided by a browser with a file
    upload, and turn it into something that is safe for opening.

    Adapted from werkzeug's secure_filename(), copyright 2007 the Pallets team.
    https://palletsprojects.com/p/werkzeug/
    """
    if '/' in name:
        name = name[name.rindex('/') + 1:]
    if sys.platform == 'win32' and '\\' in name:
        # It seems that IE gets that wrong, at least when the file is from
        # a network share
        name = name[name.rindex('\\') + 1:]
    name = _not_ascii_re.sub('', name).strip('._')
    if not name:
        return '_'
    if os.name == 'nt' and name.split('.')[0].upper() in _windows_device_files:
        name = '_' + name
    return name


class DocumentAdd(BaseHandler):
    @authenticated
    async def post(self, project_id):
        project = self.get_project(project_id)

        name = self.get_body_argument('name')
        description = self.get_body_argument('description')
        file = self.request.files['file'][0]
        content_type = file.content_type
        filename = secure_filename(file.filename)

        try:
            body = await convert.to_html_chunks(file.body, content_type,
                                                filename)
        except convert.ConversionError as err:
            self.set_status(400)
            self.send_json({
                'error': str(err),
            })
        else:
            doc = database.Document(
                name=name,
                description=description,
                filename=filename,
                project=project,
                contents=body,
            )
            self.db.add(doc)
            self.db.flush()  # Need to flush to get doc.id
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


class DocumentUpdate(BaseHandler):
    @authenticated
    def post(self, project_id, document_id):
        obj = self.get_json()
        document = self.get_document(project_id, document_id)
        if obj:
            if 'name' in obj:
                document.name = obj['name']
            if 'description' in obj:
                document.description = obj['description']
            cmd = database.Command.document_add(
                self.current_user,
                document,
            )
            self.db.add(cmd)
            self.db.commit()
            self.db.refresh(cmd)
            self.application.notify_project(document.project_id, cmd)

        self.send_json({'id': document.id})

    @authenticated
    def delete(self, project_id, document_id):
        document = self.get_document(project_id, document_id)
        self.db.delete(document)
        cmd = database.Command.document_delete(
            self.current_user,
            document,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(document.project_id, cmd)

        self.set_status(204)
        self.finish()


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
                 'end_offset': hl.end_offset,
                 'tags': [t.id for t in hl.tags]}
                for hl in document.highlights
            ],
        })


class TagAdd(BaseHandler):
    @authenticated
    def post(self, project_id):
        obj = self.get_json()
        project = self.get_project(project_id)
        tag = database.Tag(project=project,
                           path=obj['path'], description=obj['description'])
        try:
            self.db.add(tag)
            self.db.flush()  # Need to flush to get tag.id
        except IntegrityError:
            self.db.rollback()
            self.set_status(409)
            return self.finish()
        cmd = database.Command.tag_add(
            self.current_user,
            tag,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(project.id, cmd)

        self.send_json({'id': tag.id})


class TagUpdate(BaseHandler):
    @authenticated
    def post(self, project_id, tag_id):
        obj = self.get_json()
        project = self.get_project(project_id)
        tag = self.db.query(database.Tag).get(int(tag_id))
        if tag.project_id != project.id:
            raise HTTPError(404)
        if obj:
            if 'path' in obj:
                tag.path = obj['path']
            if 'description' in obj:
                tag.description = obj['description']
            cmd = database.Command.tag_add(
                self.current_user,
                tag,
            )
            try:
                self.db.add(cmd)
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                self.set_status(409)
                return self.finish()
            self.db.refresh(cmd)
            self.application.notify_project(project.id, cmd)

        self.send_json({'id': tag.id})

    @authenticated
    def delete(self, project_id, tag_id):
        project = self.get_project(project_id)
        tag = self.db.query(database.Tag).get(int(tag_id))
        if tag.project_id != project.id:
            raise HTTPError(404)
        self.db.delete(tag)
        cmd = database.Command.tag_delete(
            self.current_user,
            project.id,
            tag.id,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(project.id, cmd)

        self.set_status(204)
        self.finish()


class HighlightAdd(BaseHandler):
    @authenticated
    def post(self, project_id, document_id):
        obj = self.get_json()
        document = self.get_document(project_id, document_id, True)
        start, end = obj['start_offset'], obj['end_offset']
        snippet = extract.extract(document.contents, start, end)
        hl = database.Highlight(document=document,
                                start_offset=start,
                                end_offset=end,
                                snippet=snippet)
        self.db.add(hl)
        self.db.flush()  # Need to flush to get hl.id
        self.db.bulk_insert_mappings(database.HighlightTag, [
            dict(
                highlight_id=hl.id,
                tag_id=tag,
            )
            for tag in obj.get('tags', [])
        ])
        cmd = database.Command.highlight_add(
            self.current_user,
            document,
            hl,
            obj.get('tags', []),
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
        if obj:
            if 'start_offset' in obj:
                hl.start_offset = obj['start_offset']
            if 'end_offset' in obj:
                hl.end_offset = obj['end_offset']
            if 'tags' in obj:
                (
                    self.db.query(database.HighlightTag)
                    .filter(database.HighlightTag.highlight == hl)
                ).delete()
                self.db.bulk_insert_mappings(database.HighlightTag, [
                    dict(
                        highlight_id=hl.id,
                        tag_id=tag,
                    )
                    for tag in obj.get('tags', [])
                ])
            cmd = database.Command.highlight_add(
                self.current_user,
                document,
                hl,
                obj.get('tags', []),
            )
            self.db.add(cmd)
            self.db.commit()
            self.db.refresh(cmd)
            self.application.notify_project(document.project_id, cmd)

        self.send_json({'id': hl.id})

    @authenticated
    def delete(self, project_id, document_id, highlight_id):
        document = self.get_document(project_id, document_id)
        hl = self.db.query(database.Highlight).get(int(highlight_id))
        if hl.document_id != document.id:
            raise HTTPError(404)
        self.db.delete(hl)
        cmd = database.Command.highlight_delete(
            self.current_user,
            document,
            hl.id,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(document.project_id, cmd)

        self.set_status(204)
        self.finish()


class Highlights(BaseHandler):
    @authenticated
    def get(self, project_id, path):
        project = self.get_project(project_id)

        tag = aliased(database.Tag)
        hltag = aliased(database.HighlightTag)
        highlights = (
            self.db.query(database.Highlight)
            .join(hltag, hltag.highlight_id == database.Highlight.id)
            .join(tag, hltag.tag_id == tag.id)
            .filter(tag.path.startswith(path))
            .filter(tag.project == project)
        ).all()

        self.send_json({
            'highlights': [
                {
                    'id': hl.id,
                    'document_id': hl.document_id,
                    'content': hl.snippet,
                    'tags': [t.id for t in hl.tags],
                }
                for hl in highlights
            ],
        })


class ExportHighlightsDoc(BaseHandler):
    @authenticated
    @export_doc
    def get(self, project_id, path):
        project = self.get_project(project_id)

        tag = aliased(database.Tag)
        hltag = aliased(database.HighlightTag)
        highlights = (
            self.db.query(database.Highlight)
            .options(joinedload(database.Highlight.document))
            .join(hltag, hltag.highlight_id == database.Highlight.id)
            .join(tag, hltag.tag_id == tag.id)
            .filter(tag.path.startswith(path))
            .filter(tag.project == project)
        ).all()

        html = self.render_string('export_highlights.html', path=path,
                                  highlights=highlights)
        return 'path', html


def merge_overlapping_ranges(ranges):
    """Merge overlapping ranges in a sequence.
    """
    ranges = iter(ranges)
    try:
        merged = [next(ranges)]
    except StopIteration:
        return []

    for rg in ranges:
        left = right = bisect.bisect_right(merged, rg)
        # Merge left
        while left >= 1 and rg[0] <= merged[left - 1][1]:
            rg = (min(rg[0], merged[left - 1][0]),
                  max(rg[1], merged[left - 1][1]))
            left -= 1
        # Merge right
        while (right < len(merged) and
               merged[right][0] <= rg[1]):
            rg = (min(rg[0], merged[right][0]),
                  max(rg[1], merged[right][1]))
            right += 1
        # Insert
        if left == right:
            merged.insert(left, rg)
        else:
            merged[left:right] = [rg]

    return merged


class ExportDocument(BaseHandler):
    @authenticated
    @export_doc
    def get(self, project_id, document_id):
        doc = self.get_document(project_id, document_id, True)

        highlights = merge_overlapping_ranges((hl.start_offset, hl.end_offset)
                                              for hl in doc.highlights)

        html = self.render_string(
            'export_document.html',
            name=doc.name,
            contents=Markup(extract.highlight(doc.contents, highlights)),
        )
        return doc.name, html


class ExportCodebookCsv(BaseHandler):
    @authenticated
    def get(self, project_id):
        project = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type', 'text/csv; charset=utf-8')
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.csv"')
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['tag', 'description'])
        for tag in tags:
            writer.writerow([tag.path, tag.description])
        self.finish(buf.getvalue())


class ExportCodebookDoc(BaseHandler):
    @authenticated
    @export_doc
    def get(self, project_id):
        project = self.get_project(project_id)
        tags = list(project.tags)
        html = self.render_string('export_codebook.html', tags=tags)
        return 'codebook', html


class ProjectEvents(BaseHandler):
    @authenticated
    async def get(self, project_id):
        from_id = int(self.get_query_argument('from'))
        project = self.get_project(project_id)
        self.project_id = int(project_id)

        # Check for immediate update
        cmd = (
            self.db.query(database.Command)
            .filter(database.Command.id > from_id)
            .filter(database.Command.project_id == project.id)
            .limit(1)
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
        elif type_ == 'document_delete':
            result = {'document_delete': [cmd.document_id]}
        elif type_ == 'highlight_add':
            result = {'highlight_add': {cmd.document_id: [payload]}}
        elif type_ == 'highlight_delete':
            result = {
                'highlight_delete': {cmd.document_id: [payload['id']]}
            }
        elif type_ == 'tag_add':
            result = {
                'tag_add': [payload],
            }
        elif type_ == 'tag_delete':
            result = {
                'tag_delete': [payload['id']],
            }
        else:
            raise ValueError("Unknown command type %r" % type_)

        result['id'] = cmd.id
        self.send_json(result)

    def on_connection_close(self):
        self.wait_future.cancel()
        self.application.unobserve_project(self.project_id, self.wait_future)


class Application(tornado.web.Application):
    def __init__(self, handlers, db_url, multiuser, cookie_secret,
                 register_enabled=True, **kwargs):
        # Don't reuse the secret
        cookie_secret = cookie_secret + (
            '.multi' if multiuser
            else '.single'
        )

        super(Application, self).__init__(handlers,
                                          cookie_secret=cookie_secret,
                                          **kwargs)

        self.multiuser = multiuser
        self.register_enabled = register_enabled

        self.DBSession = database.connect(db_url)
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
            if self.multiuser:
                self._set_password(admin)
            db.add(admin)
            db.commit()
        elif self.multiuser and not admin.hashed_password:
            self._set_password(admin)
            db.commit()

        if self.multiuser:
            self.single_user_token = None
            logging.info("Starting in multi-user mode")
        else:
            self.single_user_token = hmac.new(
                cookie_secret.encode('utf-8'),
                b'taguette_single_user',
                digestmod=hashlib.sha256,
            ).hexdigest()

        # Get messages from taguette.fr
        self.messages = []
        self.check_messages()

    async def _check_messages(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    'https://msg.taguette.fr/%s' % version,
                    headers={'Accept': 'application/json'}) as response:
                obj = await response.json()
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


def make_app(db_url, multiuser, register_enabled=True, debug=False):
    if 'XDG_CACHE_HOME' in os.environ:
        cache = os.environ['XDG_CACHE_HOME']
    else:
        cache = os.path.expanduser('~/.cache')
    os.makedirs(cache, 0o700, exist_ok=True)
    cache = os.path.join(cache, 'taguette.json')
    secret = None
    try:
        fp = open(cache)
    except IOError:
        pass
    else:
        try:
            secret = json.load(fp)['cookie_secret']
            fp.close()
        except Exception:
            logger.exception("Couldn't load cookie secret from cache file")
        if not isinstance(secret, str) or not 10 <= len(secret) < 2048:
            logger.error("Invalid cookie secret in cache file")
            secret = None
    if secret is None:
        secret = os.urandom(30).decode('iso-8859-15')
        try:
            fp = open(cache, 'w')
            json.dump({'cookie_secret': secret}, fp)
            fp.close()
        except IOError:
            logger.error("Couldn't open cache file, cookie secret won't be "
                         "persisted! Users will be logged out if you restart "
                         "the program.")

    return Application(
        [
            # Basic pages
            URLSpec('/', Index, name='index'),
            URLSpec('/login', Login, name='login'),
            URLSpec('/logout', Logout, name='logout'),
            URLSpec('/register', Register, name='register'),
            URLSpec('/project/new', ProjectAdd, name='new_project'),

            # Project view
            URLSpec('/project/([0-9]+)', Project, name='project'),
            URLSpec('/project/([0-9]+)/document/[0-9]+', Project,
                    name='project_doc'),
            URLSpec('/project/([0-9]+)/highlights/[^/]*', Project,
                    name='project_tag'),

            # Export options
            URLSpec('/project/([0-9]+)/export/codebook.csv',
                    ExportCodebookCsv, name='export_codebook_csv'),
            URLSpec('/project/([0-9]+)/export/codebook.([a-z0-3]{2,4})',
                    ExportCodebookDoc, name='export_codebook_doc'),
            URLSpec('/project/([0-9]+)/export/document/'
                    '([^/]+)\\.([a-z0-9]{2,4})',
                    ExportDocument, name='export_document'),
            URLSpec('/project/([0-9]+)/export/highlights/'
                    '([^/]*)\\.([a-z0-3]{2,4})',
                    ExportHighlightsDoc, name='export_highlights_doc'),

            # API
            URLSpec('/api/project/([0-9]+)', ProjectMeta),
            URLSpec('/api/project/([0-9]+)/document/new', DocumentAdd),
            URLSpec('/api/project/([0-9]+)/document/([0-9]+)', DocumentUpdate),
            URLSpec('/api/project/([0-9]+)/document/([0-9]+)/content',
                    DocumentContents),
            URLSpec('/api/project/([0-9]+)/document/([0-9]+)/highlight/new',
                    HighlightAdd),
            URLSpec(
                '/api/project/([0-9]+)/document/([0-9]+)/highlight/([0-9]+)',
                HighlightUpdate),
            URLSpec('/api/project/([0-9]+)/highlights/([^/]*)', Highlights),
            URLSpec('/api/project/([0-9]+)/tag/new', TagAdd),
            URLSpec('/api/project/([0-9]+)/tag/([0-9]+)', TagUpdate),
            URLSpec('/api/project/([0-9]+)/events', ProjectEvents),
        ],
        static_path=pkg_resources.resource_filename('taguette', 'static'),
        login_url='/login',
        xsrf_cookies=True,
        debug=debug,
        multiuser=multiuser,
        register_enabled=register_enabled,
        cookie_secret=secret,
        db_url=db_url,
    )
